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

def reverse_move(agent, direction):
    """ Exécute le mouvement inverse pour revenir au point de départ immédiatement après un test. """
    if direction == UP:
        move(agent, DOWN)
    elif direction == DOWN:
        move(agent, UP)
    elif direction == LEFT:
        move(agent, RIGHT)
    elif direction == RIGHT:
        move(agent, LEFT)

def search_key_and_box(agent):
    """
    Version corrigée respectant STRICTEMENT la logique :
    - Boucle 2 fois (suffisant pour passer de 0.25 -> 0.5 -> 1.0)
    - Scan des 4 voisins
    - Si plusieurs max, on fait TOUS les mouvements (diagonale implicite)
    """
    
    # Dictionnaire pour revenir en arrière instantanément sans recalculer de pathfinding
    opposites = {UP: DOWN, DOWN: UP, LEFT: RIGHT, RIGHT: LEFT}

    for i in range(2): 
        # --- PHASE 1 : SCAN ---
        dict_moves = {}
        
        # On teste les 4 directions
        for direction in [UP, DOWN, LEFT, RIGHT]:
            # 1. On avance pour tester
            move(agent, direction)
            
            # 2. On note la valeur
            # On utilise .get() pour éviter un crash si la clé manque
            val = agent.msg.get("cell_val", 0.0)
            dict_moves[direction] = val
            
            # 3. On revient TOUT DE SUITE à la case départ du tour
            # Ne surtout pas utiliser move_to() ici, c'est trop lent/complexe
            move(agent, opposites[direction])

        # --- PHASE 2 : ANALYSE ---
        max_value = max(dict_moves.values())
        
        # Si on a perdu la trace (que des 0), on arrête
        if max_value == 0.0:
            break

        # On récupère TOUTES les directions qui ont la valeur max
        best_moves = [
            key
            for key, value in dict_moves.items() # Parcourir chaque paire clé-valeur
            if value == max_value                # Conserver uniquement si la valeur est le maximum
        ]# revient a etre une liste avec les direction a prendre
        for move_direction in best_moves:
            move(agent, move_direction)
    #check id key or box found
    cell_value = agent.msg["cell_val"]
    if cell_value == KEY_TYPE:
        found_element_add(agent, agent.x, agent.y, KEY_TYPE)
    elif cell_value == BOX_TYPE:
        found_element_add(agent, agent.x, agent.y, BOX_TYPE)   
def search_key_and_box2(agent):
    """ Function that makes the agent search for its key and box in the environment """
    """
    idée de comment faire :
    si le robot détecte une case avec une valeur de 0.25, alors il va essayer les case 
    haut bas gauche droite en envoyant un msg[cell_value] pour chaque case
    il crée un dictionnaire avec up, down, left, right et la valeur de chaque case
    ensuite il regarde dans ce dictionnaire et recherche la valeur la plus élevée, 
    si la valeur max est unique alors on va dans cette direction, si on voit qu'il y a plusieurs valeurs max
    alors on réalise les deux déplacements
    on se retrouve donc alors toujours dans le prochain zone, on répète l'opération et on trouvera la clé 

    """
    for i in range(2): 
        dict_moves = {UP: None, DOWN: None, LEFT: None, RIGHT: None}
        pos_initiale = (agent.x, agent.y)
        move(agent, UP)
        dict_moves[UP] = agent.msg["cell_val"]
        move_to(agent, pos_initiale[0], pos_initiale[1])  # Retour à la position initiale
        move(agent, DOWN)
        dict_moves[DOWN] = agent.msg["cell_val"]
        move_to(agent, pos_initiale[0], pos_initiale[1]) 
        move(agent, LEFT)
        dict_moves[LEFT] = agent.msg["cell_val"]
        move_to(agent, pos_initiale[0], pos_initiale[1]) 
        move(agent, RIGHT)
        dict_moves[RIGHT] = agent.msg["cell_val"]
        move_to(agent, pos_initiale[0], pos_initiale[1])
        max_value = max(dict_moves.values())
        print(max_value)
        best_moves = [
            key
            for key, value in dict_moves.items() # Parcourir chaque paire clé-valeur
            if value == max_value                # Conserver uniquement si la valeur est le maximum
        ]# revient a etre une liste avec les direction a prendre
        for move_direction in best_moves:
            move(agent, move_direction)
    #check id key or box found
    cell_value = agent.msg["cell_val"]
    if cell_value == KEY_TYPE:
        found_element_add(agent, agent.x, agent.y, KEY_TYPE)
    elif cell_value == BOX_TYPE:
        found_element_add(agent, agent.x, agent.y, BOX_TYPE)    


    




    

        
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
    
    W,H = agent1.w, agent1.h

    # Map Discovery Loop
    for i in range (5):
        move(agent1, RIGHT)
        if agent1.msg["cell_val"] == 0.25:
           search_key_and_box(agent1)
    time.sleep(2000) 


