import sys
from server import Server
from agent import Agent
from my_constants import *
from random import randint
import time
import math

def move(agent, direction):
    agent.network.send({"header": MOVE, "direction": direction})

def move_to(agent, x, y):
    for i in range(abs(agent.x - x)):
        if agent.x < x:
            direction = RIGHT
        else:
            direction = LEFT
        move(agent, direction)
        time.sleep(0.1)
    for i in range(abs(agent.y - y)):
        if agent.y < y:
            direction = DOWN
        else:
            direction = UP
        move(agent, direction)
        time.sleep(0.1)
    agent.network.send({"header": MOVE_TO, direction: y})
if __name__ == "__main__":

    port = 5555
    ip_server = "localhost"
    nb_agents = 2
    map_id = 1
    
    agent1 = Agent(ip_server)
    agent2 = Agent(ip_server)
    
    try:
        screen_width, screen_height = agent1.w, agent1.h
        # Calculate the best trajectory based on the environment dimensions

        nb_carrés = math.ceil(screen_height / 5)
        carre_size = 5  # Size of each square in the trajectory
        print(f"Environment dimensions: width={screen_width}, height={screen_height}")

        iteration = 0
        direction_x = LEFT
        direction_y = DOWN
        while True:
            # Gestion des déplacements horizontaux si largeur diagonale
            if iteration % carre_size == 0 and direction_x==RIGHT:
                direction_x = LEFT
            elif iteration % carre_size == 0 and direction_x==LEFT:
                direction_x = RIGHT
            
            # Gestion des déplacements verticaux si hauteur totale atteinte
            if iteration % screen_height == 0 and direction_y==DOWN and iteration != 0:
                direction_y = UP
                for i in range(carre_size*2-1):
                    agent1.network.send({"header": MOVE, "direction": RIGHT})  # Move up one extra step to start new line
                    time.sleep(0.1)
            elif iteration % screen_height == 0 and direction_y==UP and iteration != 0:
                direction_y = DOWN
                for i in range(carre_size*2-1):
                    agent1.network.send({"header": MOVE, "direction": RIGHT})  # Move down one extra step to start new line
                    time.sleep(0.1)
            move(agent1, direction_x)
            move(agent1, direction_y)
            time.sleep(0.25)  # Small delay to visualize the movement
            iteration += 1


    except Exception as e:
        print(f"An error occurred: {e}")