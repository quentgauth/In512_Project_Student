import sys
from server import Server
from agent import Agent
from my_constants import *
from random import randint
import time
import math
import warnings
import numpy as np
import threading

elements_trouves = []
last_move = None

def move(agent, direction):
    agent.network.send({"header": MOVE, "direction": direction})
    time.sleep(0.1)  #wait for the server to process the move
    global last_move
    last_move = direction
    
    agent.nbre_move += 1

def get_data(agent):
    agent.network.send({"header": GET_DATA})
    time.sleep(0.1)  #wait for the server to process the request
    data = agent.msg
    return data

def move_to(agent, x, y, find_objects=False):
    """ Function that makes the agent move to the specified (x, y) position """
    
    if abs(agent.x - x) and abs(agent.y - y) != 0:
        if agent.x < x and agent.y < y:
            for i in range(min(abs(agent.x - x), abs(agent.y - y))):
                move(agent, DOWN_RIGHT)  # Diagonal move to reduce both x and y distance
        elif agent.x < x and agent.y > y:
            for i in range(min(abs(agent.x - x), abs(agent.y - y))):
                move(agent, UP_RIGHT)
        elif agent.x > x and agent.y < y:
            for i in range(min(abs(agent.x - x), abs(agent.y - y))):
                move(agent, DOWN_LEFT)
        elif agent.x > x and agent.y > y:
            for i in range(min(abs(agent.x - x), abs(agent.y - y))):
                move(agent, UP_LEFT)
    
    # Move in x direction
    for i in range(abs(agent.x - x)):
        if agent.x < x:
            direction = RIGHT
        else:
            direction = LEFT
        move(agent, direction)

    # Move in y direction
    for i in range(abs(agent.y - y)):
        if agent.y < y:
            direction = DOWN
        else:
            direction = UP   
        move(agent, direction)
        
def search_map(agent):
    move_to(agent, agent.start_x, 0)

    mult_x = -1
    mult_y = -1

    for i in range(0,12):
        if agent.x == agent.end_x or agent.x == agent.start_x:
            mult_x *= -1

            # Calculer la taille du carré à parcourir en fonction de la direction
            if mult_y == -1 and mult_x == 1:
                square_size = min((agent.y - 0), (agent.end_x - agent.x))
            elif mult_y == 1 and mult_x ==1:
                square_size = min((agent.h - agent.y), (agent.end_x- agent.x))

            elif mult_y == -1 and mult_x == -1:
                square_size = min((agent.y - 0), agent.x - agent.start_x)

            elif mult_y == 1 and mult_x == -1:
                square_size = min((agent.h - agent.y), agent.x - agent.start_x)

            # Valeurs à ajouter aux coordonnées actuelles pour le déplacemen
            add_x = square_size * mult_x
            add_y = square_size * mult_y
        
        if agent.y == agent.h or agent.y ==0:

            # Changer de direction en y
            mult_y *= -1

            # Calculer la taille du carré à parcourir en fonction de la direction
            if mult_y == -1 and mult_x == 1:
                square_size = min((agent.y - 0), (agent.end_x - agent.x))
            elif mult_y == 1 and mult_x ==1:
                square_size = min((agent.h - agent.y), (agent.end_x - agent.x))

            elif mult_y == -1 and mult_x == -1:
                square_size = min((agent.y - 0), agent.x - agent.start_x)

            elif mult_y == 1 and mult_x == -1:
                square_size = min((agent.h - agent.y), agent.x - agent.start_x)

            # Valeurs à ajouter aux coordonnées actuelles pour le déplacement
            add_y = square_size * mult_y
            add_x = square_size * mult_x
        
        print(f"Robot from ({agent.x},{agent.y}) moving to ({agent.x + add_x},{agent.y + add_y}) with square size {square_size}")
        move_to(agent, agent.x + add_x, agent.y + add_y)


def search_map2(agent):
    move_to(agent, agent.start_x, 0)

    mult_x = -1
    mult_y = -1

    square_size = 8

    for i in range(0,12):
        if agent.x == agent.end_x or agent.x == agent.start_x:
            mult_x *= -1

            # Valeurs à ajouter aux coordonnées actuelles pour le déplacemen
            add_x = square_size * mult_x
            add_y = square_size * mult_y
        
        if agent.y == agent.h or agent.y ==0:

            # Changer de direction en y
            mult_y *= -1

            # Valeurs à ajouter aux coordonnées actuelles pour le déplacement
            add_y = square_size * mult_y
            add_x = square_size * mult_x

        print(f"Robot from ({agent.x},{agent.y}) moving to ({agent.x + add_x},{agent.y + add_y}) with square size {square_size}")
        move_to(agent, agent.x + add_x, agent.y + add_y)


if __name__ == "__main__":

    port = 5555
    ip_server = "localhost"
    nb_agents = 2
    
    agents = []
    for i in range(nb_agents):
        agent = Agent(ip_server)
        agents.append(agent)

    map_w, map_h = agents[0].w, agents[0].h

    w = map_w//nb_agents

    # Modifier les attributs de chaque agent pour diviser la carte
    for i in range(nb_agents):
        agents[i].w = w *i
        agents[i].h = map_h - 1
        agents[i].start_x = w * i
        agents[i].end_x = w * (i + 1)

        # Initialiser le compteur de mouvements pour chaque agent
        agents[i].nbre_move = 0

    # Map Discovery Loop
    for agent in agents:
        threading.Thread(target=search_map, args=(agent,)).start()
        time.sleep(1)
    # threading.Thread(target=search_map, args=(agents[0],)).start()

    # search_map(agents[0])
    # print("Number of moves made:", agents[1].nbre_move)