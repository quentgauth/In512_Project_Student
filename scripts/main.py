import sys
from server import Server
from agent import Agent
from my_constants import *
from random import randint
import time
import math
import warnings
import numpy as np

elements_trouves = []
last_move = None
agent_progress = {}  # track per-agent discovery state

# Directions helpers to reason about local probing
DIR_OFFSETS = {
    STAND: (0, 0),
    LEFT: (-1, 0),
    RIGHT: (1, 0),
    UP: (0, -1),
    DOWN: (0, 1),
    UP_LEFT: (-1, -1),
    UP_RIGHT: (1, -1),
    DOWN_LEFT: (-1, 1),
    DOWN_RIGHT: (1, 1),
}
OPPOSITE_DIR = {
    STAND: STAND,
    LEFT: RIGHT,
    RIGHT: LEFT,
    UP: DOWN,
    DOWN: UP,
    UP_LEFT: DOWN_RIGHT,
    UP_RIGHT: DOWN_LEFT,
    DOWN_LEFT: UP_RIGHT,
    DOWN_RIGHT: UP_LEFT,
}
# When we détect a halo, prioritize probing around the last move to reduce travel
SCAN_PRIORITIES = {
    LEFT: [LEFT, UP_LEFT, DOWN_LEFT, UP, DOWN, UP_RIGHT, DOWN_RIGHT, RIGHT],
    RIGHT: [RIGHT, UP_RIGHT, DOWN_RIGHT, UP, DOWN, UP_LEFT, DOWN_LEFT, LEFT],
    UP: [UP, UP_LEFT, UP_RIGHT, LEFT, RIGHT, DOWN_LEFT, DOWN_RIGHT, DOWN],
    DOWN: [DOWN, DOWN_LEFT, DOWN_RIGHT, LEFT, RIGHT, UP_LEFT, UP_RIGHT, UP],
}
DEFAULT_SCAN_ORDER = [UP, DOWN, LEFT, RIGHT, UP_LEFT, UP_RIGHT, DOWN_LEFT, DOWN_RIGHT]

def move(agent, direction):
    agent.network.send({"header": MOVE, "direction": direction})
    time.sleep(0.1)  #wait for the server to process the move
    global last_move
    last_move = direction

def get_data(agent):
    agent.network.send({"header": GET_DATA})
    time.sleep(0.1)  #wait for the server to process the request
    data = agent.msg
    return data

def probe_neighbors(agent, scan_order):
    """
    Probe surrounding cells following scan_order (list of direction constants).
    Moves out-and-back for each candidate to keep the agent at its starting pose.
    Returns (best_dir, best_val).
    """
    current_val = get_data(agent)["cell_val"]
    best_val = current_val
    best_dir = None

    for direction in scan_order:
        move(agent, direction)
        val = get_data(agent)["cell_val"]
        if val > best_val:
            best_val = val
            best_dir = direction
        # return to the origin to avoid drifting during probing
        move(agent, OPPOSITE_DIR[direction])
    return best_dir, best_val

def scan_local_area(agent, radius, target_type):
    """
    Deterministic serpentine scan of the square centered on the agent with given radius.
    Visits each cell within Chebyshev distance <= radius, early-exits on target found.
    """
    start_x, start_y = agent.x, agent.y
    w, h = agent.w, agent.h

    for dy in range(-radius, radius + 1):
        xs = list(range(-radius, radius + 1))
        if dy % 2 != 0:
            xs.reverse()  # serpentine to reduce backtracking
        for dx in xs:
            tx, ty = start_x + dx, start_y + dy
            if not (0 <= tx < w and 0 <= ty < h):
                continue
            if tx == agent.x and ty == agent.y:
                cell_val = get_data(agent)["cell_val"]
            else:
                move_to(agent, tx, ty, find_objects=False)
                cell_val = get_data(agent)["cell_val"]
            if cell_val == np.float64(1.0):
                found_element_add(agent, agent.x, agent.y, target_type)
                return True
    # return to starting point after scan
    move_to(agent, start_x, start_y, find_objects=False)
    return False

def get_progress(agent):
    """Return mutable progress dict for this agent."""
    if agent.agent_id not in agent_progress:
        agent_progress[agent.agent_id] = {"key_found": False, "box_found": False}
    return agent_progress[agent.agent_id]

# def diagonal_move(agent, target_x, target_y):
#     while agent.x != target_x and agent.y != target_y:
#         if agent.x < target_x and agent.y < target_y:
#             move(agent, DOWN_RIGHT)
#         elif agent.x < target_x and agent.y > target_y:
#             move(agent, UP_RIGHT)
#         elif agent.x > target_x and agent.y < target_y:
#             move(agent, DOWN_LEFT)
#         elif agent.x > target_x and agent.y > target_y:
#             move(agent, UP_LEFT)

def move_to(agent, x, y, find_objects=True):
    """ Function that makes the agent move to the specified (x, y) position """
    
    if abs(agent.x - x) and abs(agent.y - y) != 0:
        if agent.x < x and agent.y < y:
            for i in range(min(abs(agent.x - x), abs(agent.y - y))):
                move(agent, DOWN_RIGHT)  # Diagonal move to reduce both x and y distance
                if find_objects:
                    search_key_and_box(agent)
        elif agent.x < x and agent.y > y:
            for i in range(min(abs(agent.x - x), abs(agent.y - y))):
                move(agent, UP_RIGHT)
                if find_objects:
                    search_key_and_box(agent)
        elif agent.x > x and agent.y < y:
            for i in range(min(abs(agent.x - x), abs(agent.y - y))):
                move(agent, DOWN_LEFT)
                if find_objects:
                    search_key_and_box(agent)
        elif agent.x > x and agent.y > y:
            for i in range(min(abs(agent.x - x), abs(agent.y - y))):
                move(agent, UP_LEFT)
                if find_objects:
                    search_key_and_box(agent)
    
    # Move in x direction
    for i in range(abs(agent.x - x)):
        if agent.x < x:
            direction = RIGHT
        else:
            direction = LEFT
        move(agent, direction)
        if find_objects:
            search_key_and_box(agent)

    # Move in y direction
    for i in range(abs(agent.y - y)):
        if agent.y < y:
            direction = DOWN
        else:
            direction = UP   
        move(agent, direction)

def search_map(agent):
    # Raccourcis
    W = agent.w      # largeur fenêtre en nombre de cases
    H = agent.h      # hauteur fenêtre en nombre de cases

    # 1. Définir les pas
    STEP = 8


    # 1. Start en haut-gauche
    move_to(agent, 0, 0)

    for i in range(0, W, STEP):

        if agent.y == 0:
            move_to(agent, i, 0)
            move_to(agent, 0, i)
            
        elif agent.x ==0:
            move_to(agent, 0, i)
            move_to(agent, i, 0)
        

        # for i in range(0, w, step):



        #     if agent.x == 0:
        #         move_to(agent, i,0)
        #         move_to(agent, i+step_find,0)
        #         move_to(agent,  i-step_find,0)

        #     if agent.y == 0:
        #         move_to(agent, 0,i)
        #         move_to(agent, 0,i+step)

        #         move_to(agent, 0, i+step_find)
        #         move_to(agent, 0, i-step_find)




        # move_to(agent1, 9, 0)

        # move_to(agent1, 13, 0)

        # move_to(agent1, 9, 0)

        # move_to(agent1, 0, 9)

        # move_to(agent1, 0,18)

        # move_to(agent1, 18,0)
        
def search_key_and_box(agent):
    """
    When we stand on a halo (0.25/0.3/0.5/0.6), scan the known halo square
    (radius 1 or 2) with minimal moves to reach the item (cell_val == 1),
    then resume the global sweep.
    """
    current_val = get_data(agent)["cell_val"]
    if current_val not in [0.25, 0.3, 0.5, 0.6]:
        return

    progress = get_progress(agent)
    is_key_halo = current_val in [0.25, 0.5]
    is_box_halo = current_val in [0.3, 0.6]

    # If we've already found this type, ignore its halo to continue the global sweep
    if (is_key_halo and progress["key_found"]) or (is_box_halo and progress["box_found"]):
        return

    target_type = KEY_TYPE if is_key_halo else BOX_TYPE
    radius = 1 if current_val in [0.5, 0.6] else 2
    found = scan_local_area(agent, radius, target_type)
    if not found:
        # fallback to short gradient climb if scan did not hit (robustness)
        scan_order = SCAN_PRIORITIES.get(last_move, DEFAULT_SCAN_ORDER)
        best_dir, best_val = probe_neighbors(agent, scan_order)
        if best_val > current_val and best_dir is not None:
            move(agent, best_dir)
            if get_data(agent)["cell_val"] == np.float64(1.0):
                found_element_add(agent, agent.x, agent.y, target_type)
                return
    
def found_element_add(agent,x, y,key):
    """ Function that adds the squares found to the list of found elements if not already present """   
    data = {"coordinates":None,"type": key}
    agent.network.send({"header": KEY_DISCOVERED if key==KEY_TYPE else BOX_DISCOVERED, "x": x, "y": y})
    progress = get_progress(agent)
    if key == KEY_TYPE:
        progress["key_found"] = True
    else:
        progress["box_found"] = True
    if (x, y) not in elements_trouves:
        square_coordinates = [(x + dx, y + dy) for dx in range(-2, 3) for dy in range(-2, 3)]
        data["coordinates"] = square_coordinates
        elements_trouves.append(data)

if __name__ == "__main__":

    port = 5555
    ip_server = "localhost"
    nb_agents = 2
    map_id = 1
    
    agent1 = Agent(ip_server)
    agent2 = Agent(ip_server)
    
    w, h = agent1.w, agent1.h

    # Map Discovery Loop

    search_map(agent1)
