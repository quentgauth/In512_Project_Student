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

def diagonal_move(agent, target_x, target_y):
    while agent.x != target_x and agent.y != target_y:
        if agent.x < target_x and agent.y < target_y:
            move(agent, DOWN_RIGHT)
        elif agent.x < target_x and agent.y > target_y:
            move(agent, UP_RIGHT)
        elif agent.x > target_x and agent.y < target_y:
            move(agent, DOWN_LEFT)
        elif agent.x > target_x and agent.y > target_y:
            move(agent, UP_LEFT)

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
    """ Function that makes the agent search for its key and box in the environment """

    # Cell value before searching
    prev_cell_val = get_data(agent)["cell_val"]
    if prev_cell_val not in [0.25, 0.3]:
        return
    
    allowed_moves = {
        0: "STAND",
        1: "LEFT",
        2: "RIGHT",
        3: "UP",
        4: "DOWN",
        5: "UP_LEFT",
        6: "UP_RIGHT",
        7: "DOWN_LEFT",
        8: "DOWN_RIGHT"
    }
    move_name = allowed_moves.get(last_move, "UNKNOWN_MOVE")

    last_directions = move_name.split('_')    

    best = prev_cell_val

    # Determine le type d'élément recherché
    if prev_cell_val == np.float64(0.25):
        key = KEY_TYPE
    elif prev_cell_val == np.float64(0.3):
        key = BOX_TYPE

    directions_values = []
    while True:
        for direction in last_directions:
            move(agent, direction)
            data = get_data(agent)["cell_val"]
            directions_values.append((direction, data))

            # Retourne à la position initiale
            if direction == "UP":
                move(agent, DOWN)
            elif direction == "DOWN":
                move(agent, UP)
            elif direction == "LEFT":
                move(agent, RIGHT)
            elif direction == "RIGHT":
                move(agent, LEFT)
            
        # Trouve la meilleure direction
        best_direction, best_value = max(directions_values, key=lambda x: x[1])
        if best_value > best:
            best = best_value
            direction = best_direction
            break
        else:
            break  # Sort de la boucle si aucune amélioration n'est trouvée
            

                # if get_data(agent)["cell_val"] == np.float64(1.0):
                #     found_element_add(agent, agent.x, agent.y,key)
                #     return
        
def search_key_and_box2(agent):
    """ Function that makes the agent search for its key and box in the environment """
    prev_cell_val = get_data(agent)["cell_val"]
    if prev_cell_val not in [0.25, 0.3]:
        return

    best = prev_cell_val
    directions = []
    if prev_cell_val == np.float64(0.25):
        key = KEY_TYPE
    elif prev_cell_val == np.float64(0.3):
        key = BOX_TYPE

# TODO : Réparer cette boucle while (Regarder si toutes les directions sont bien testées (fonctionne si le robot vient d'en haut ou du bas mais pas sur les côtés))

    while True:
        
        # Bouge Bas Droite
        move(agent, DOWN_RIGHT)
        data = get_data(agent)["cell_val"]
        if data > best:
            best = data
            directions = [DOWN, RIGHT]
            
        else:
            move(agent, UP_LEFT)  # Retourne à la position initiale

            # Bouge Bas Gauche
            move(agent, UP_LEFT)
            data = get_data(agent)["cell_val"]
            if data > best:
                best = data
                directions = [UP, LEFT]
            else:
                move(agent, DOWN_RIGHT)  # Retourne à la position initiale

        
        # Bouge Haut Gauche
        move(agent, DOWN_LEFT)
        data = get_data(agent)["cell_val"]
        if data > best and LEFT in directions:
            best = data
            direction = LEFT
            break
        elif data > best and DOWN in directions:
            best = data
            direction = DOWN
            break
        else:
            move(agent, UP_RIGHT)  # Retourne à la position initiale

        # Bouge Haut Droite
        move(agent, UP_RIGHT)
        data = get_data(agent)["cell_val"]
        if data == best:
            direction = DOWN  # Par défaut si rien de mieux n'est trouvé
            break
        if data > best and RIGHT in directions:
            best = data
            direction = RIGHT
            break
        elif data > best and UP in directions:
            best = data
            direction = UP
            break
        else:
            direction = UP  # Par défaut si rien de mieux n'est trouvé
            break


    time.sleep(3)
    if direction == DOWN:

        move(agent, DOWN_LEFT)
        data = get_data(agent)["cell_val"]

        if data > best:
            found_element_add(agent, agent.x, agent.y,key)
        elif data < best:
            move(agent, RIGHT)
            move(agent, RIGHT)
            if get_data(agent)["cell_val"] == np.float64(1.0):
                found_element_add(agent, agent.x, agent.y,key)
        elif data == best:
            move(agent, RIGHT)
            if get_data(agent)["cell_val"] == np.float64(1.0):
                found_element_add(agent, agent.x, agent.y,key)

    elif direction == UP:

        move(agent, UP_LEFT)
        data = get_data(agent)["cell_val"]

        if data > best:
            found_element_add(agent, agent.x, agent.y,key)
        elif data < best:
            move(agent, RIGHT)
            move(agent, RIGHT)
            if get_data(agent)["cell_val"] == np.float64(1.0):
                found_element_add(agent, agent.x, agent.y,key)
        elif data == best:
            move(agent, RIGHT)
            if get_data(agent)["cell_val"] == np.float64(1.0):
                found_element_add(agent, agent.x, agent.y,key)

def found_element_add(agent,x, y,key):
    """ Function that adds the squares found to the list of found elements if not already present """   
    data = {"coordinates":None,"type": key}
    agent.network.send({"header": KEY_DISCOVERED if key==KEY_TYPE else BOX_DISCOVERED, "x": x, "y": y})
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

