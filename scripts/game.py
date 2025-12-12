__author__ = "Aybuke Ozturk Suri, Johvany Gustave"
__copyright__ = "Copyright 2023, IN512, IPSA 2024"
__credits__ = ["Aybuke Ozturk Suri", "Johvany Gustave"]
__license__ = "Apache License 2.0"
__version__ = "1.0.0"


import json, os
import numpy as np

from my_constants import *
from gui import GUI
from time import sleep


class Game:
    """ Handle the whole game """
    def __init__(self, nb_agents, map_id):
        self.nb_agents = nb_agents
        self.nb_ready = 0
        self.agent_id = 0
        self.moves = [(0, 0), (-1, 0), (1, 0), (0, -1), (0, 1), (-1, -1), (1, -1), (-1, 1), (1, 1)]
        self.agent_paths = [None]*nb_agents
        self.game_over = False
        self.death_position = None
        self.death_agent = None
        self.load_map(map_id)
        self.gui = GUI(self,cell_size=20)
        

    
    def load_map(self, map_id):
        """ Load a map """
        json_filename = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "resources", "config.json")
        with open(json_filename, "r") as json_file:
            self.map_cfg = json.load(json_file)[f"map_{map_id}"]        
        
        self.agents, self.keys, self.boxes = [], [], []
        for i in range(self.nb_agents):
            self.agents.append(Agent(i+1, self.map_cfg[f"agent_{i+1}"]["x"], self.map_cfg[f"agent_{i+1}"]["y"], self.map_cfg[f"agent_{i+1}"]["color"]))
            self.keys.append(Key(self.map_cfg[f"key_{i+1}"]["x"], self.map_cfg[f"key_{i+1}"]["y"]))
            self.boxes.append(Box(self.map_cfg[f"box_{i+1}"]["x"], self.map_cfg[f"box_{i+1}"]["y"]))
            self.agent_paths[i] = [(self.agents[i].x, self.agents[i].y)]
        
        # Load walls
        self.walls = []
        wall_idx = 1
        while f"wall_{wall_idx}" in self.map_cfg:
            wall_cfg = self.map_cfg[f"wall_{wall_idx}"]
            self.walls.append(Wall(wall_cfg["x"], wall_cfg["y"], wall_cfg.get("rotation", 0)))
            wall_idx += 1
        
        self.map_w, self.map_h = self.map_cfg["width"], self.map_cfg["height"]
        self.map_real = np.zeros(shape=(self.map_h, self.map_w))
        
        # First, add items (keys and boxes) to establish their zones
        items = []
        items.extend(self.keys)
        items.extend(self.boxes)
        offsets = [[(-1, -1), (0, -1), (1, -1), (-1, 0), (0, 0), (1, 0), (-1, 1), (0, 1), (1, 1)], [(-2, -2), (-1, -2), (0, -2), (1, -2), (2, -2), (-2, -1), (2, -1), (-2, 0), (2, 0), (-2, 1), ( 2, 1), (-2, 2), (-1, 2), (0, 2), (1, 2), (2, 2)]]
        for item in items:
            for i, sub_list in enumerate(offsets):
                for dx, dy in sub_list:
                    if dx != 0 or dy != 0:
                        self.add_val(item.x + dx, item.y + dy, item.neighbour_percent/(i+1))
                    else:
                        self.add_val(item.x, item.y, 1)
        
        # Store item zones to check wall placement
        self.item_zones = set()
        for item in items:
            for sub_list in offsets:
                for dx, dy in sub_list:
                    self.item_zones.add((item.x + dx, item.y + dy))
        
        # Add walls only on cells that are not in item zones
        for wall in self.walls:
            # Add warning zone (0.35) only on empty cells (not in item zones)
            for wx, wy in wall.get_warning_zone():
                if 0 <= wx < self.map_w and 0 <= wy < self.map_h:
                    if (wx, wy) not in self.item_zones and self.map_real[wy, wx] == 0:
                        self.map_real[wy, wx] = WALL_WARNING_PERCENTAGE
            # Add wall cells (1.0) only on empty cells (not in item zones)
            for wx, wy in wall.cells:
                if 0 <= wx < self.map_w and 0 <= wy < self.map_h:
                    if (wx, wy) not in self.item_zones:
                        self.map_real[wy, wx] = WALL_VALUE

    
    def add_val(self, x, y, val):
        """ Add a value if x and y coordinates are in the range [map_w; map_h] """
        if 0 <= x < self.map_w and 0 <= y < self.map_h:
            self.map_real[y, x] = val


    def process(self, msg, agent_id):
        """ Process data sent by agent whose id is specified """
        self.agent_id = agent_id
        if msg["header"] == MOVE:
            return self.handle_move(msg, agent_id)
        elif msg["header"] == GET_DATA:
            return {"sender": GAME_ID, "header": GET_DATA, "agent_id" : self.agent_id, "x": self.agents[agent_id].x, "y": self.agents[agent_id].y, "w": self.map_w, "h": self.map_h, "cell_val": self.map_real[self.agents[agent_id].y, self.agents[agent_id].x]}
        elif msg["header"] == GET_NB_CONNECTED_AGENTS:
            return {"sender": GAME_ID, "header": GET_NB_CONNECTED_AGENTS, "nb_connected_agents": self.nb_ready}
        elif msg["header"] == GET_NB_AGENTS:
            return {"sender": GAME_ID, "header": GET_NB_AGENTS, "nb_agents": self.nb_agents}
        elif msg["header"] == GET_ITEM_OWNER:
            return self.handle_item_owner_request(agent_id)
        

    def handle_move(self, msg, agent_id):
        """ Make sure the desired move is allowed and update the agent's position """
        if self.game_over:  # Don't process moves if game is over
            return {"sender": GAME_ID, "header": MOVE, "x": self.agents[agent_id].x, "y": self.agents[agent_id].y, "cell_val": self.map_real[self.agents[agent_id].y, self.agents[agent_id].x], "game_over": True}
        
        if msg["direction"] in range(9):
            dx, dy = self.moves[msg["direction"]]
            x, y = self.agents[agent_id].x, self.agents[agent_id].y
            new_x, new_y = x + dx, y + dy
            
            if 0 <= new_x < self.map_w and 0 <= new_y < self.map_h:
                # Check if target cell is a wall (not an item)
                target_val = self.map_real[new_y, new_x]
                is_wall = target_val == WALL_VALUE and self._is_wall_cell(new_x, new_y)
                
                if is_wall:
                    # GAME OVER! Agent hit a wall
                    self.game_over = True
                    self.death_position = (new_x, new_y)
                    self.death_agent = agent_id
                    print(f"💀 GAME OVER! Agent {agent_id} hit a wall at ({new_x}, {new_y})")
                    return {"sender": GAME_ID, "header": MOVE, "x": x, "y": y, "cell_val": self.map_real[y, x], "game_over": True, "death_pos": (new_x, new_y)}
                else:
                    self.agents[agent_id].x, self.agents[agent_id].y = new_x, new_y
                    if (self.agents[agent_id].x, self.agents[agent_id].y) not in self.agent_paths[agent_id]:
                        self.agent_paths[agent_id].append((self.agents[agent_id].x, self.agents[agent_id].y))
        return {"sender": GAME_ID, "header": MOVE, "x": self.agents[agent_id].x, "y": self.agents[agent_id].y, "cell_val": self.map_real[self.agents[agent_id].y, self.agents[agent_id].x], "game_over": False}
    
    def _is_wall_cell(self, x, y):
        """Check if position (x,y) is a wall cell (not an item)"""
        # Check if it's a key or box position
        for key in self.keys:
            if key.x == x and key.y == y:
                return False
        for box in self.boxes:
            if box.x == x and box.y == y:
                return False
        # Check if it's in any wall's cells
        for wall in self.walls:
            if (x, y) in wall.cells:
                return True
        return False



    def handle_item_owner_request(self, agent_id):
        if self.map_real[self.agents[agent_id].y, self.agents[agent_id].x] != 1.0:  #make sure the agent is located on an item
            return {"sender": GAME_ID, "header": GET_ITEM_OWNER, "owner": None}
        for i, key in enumerate(self.keys): #check if it's a key
            if (self.agents[agent_id].x == key.x) and (self.agents[agent_id].y == key.y):
                return  {"sender": GAME_ID, "header": GET_ITEM_OWNER, "owner": i, "type": KEY_TYPE}
        for i, box in enumerate(self.boxes):    #check if it's a box
            if (self.agents[agent_id].x == box.x) and (self.agents[agent_id].y == box.y):
                return  {"sender": GAME_ID, "header": GET_ITEM_OWNER, "owner": i, "type": BOX_TYPE}


class Agent:
    def __init__(self, id, x, y, color):
        self.id = id
        self.x, self.y = x, y
        self.color = color

    def __repr__(self):
        return f"Agent's id: {self.id}, x: {self.x}, y: {self.y}, color: {self.color}"
    

class Item:
    def __init__(self, x, y, neighbor_percent, type):
        self.x, self.y = x, y
        self.neighbour_percent = neighbor_percent
        self.type = type

    def __repr__(self):
        return f"type: {self.type}, x: {self.x}, y: {self.y}"


class Key(Item):
    def __init__(self, x, y):
        Item.__init__(self, x, y, KEY_NEIGHBOUR_PERCENTAGE, "key")
    

class Box(Item):
    def __init__(self, x, y):
        Item.__init__(self, x, y, BOX_NEIGHBOUR_PERCENTAGE, "box")


class Wall:
    """
    L-shaped wall (5 cells in a 3x3 grid) with a warning zone around it.
    Rotation determines the orientation of the L:
    - 0: ███    (top row + left column)
         █
         █
    - 1: ███    (top row + right column)
           █
           █
    - 2: █      (bottom row + left column)
         █
         ███
    - 3:   █    (bottom row + right column)
           █
         ███
    """
    def __init__(self, x, y, rotation=0):
        self.x, self.y = x, y
        self.rotation = rotation
        self.cells = self._get_cells()  # The 5 wall cells
    
    def _get_cells(self):
        """Get the 5 cell positions of the L-shape based on rotation"""
        # Each L-shape is made of 5 cells in a 3x3 grid
        if self.rotation == 0:  # Top row + left column
            return [
                (self.x, self.y), (self.x + 1, self.y), (self.x + 2, self.y),  # top row
                (self.x, self.y + 1), (self.x, self.y + 2)  # left column
            ]
        elif self.rotation == 1:  # Top row + right column
            return [
                (self.x, self.y), (self.x + 1, self.y), (self.x + 2, self.y),  # top row
                (self.x + 2, self.y + 1), (self.x + 2, self.y + 2)  # right column
            ]
        elif self.rotation == 2:  # Bottom row + left column
            return [
                (self.x, self.y), (self.x, self.y + 1),  # left column
                (self.x, self.y + 2), (self.x + 1, self.y + 2), (self.x + 2, self.y + 2)  # bottom row
            ]
        elif self.rotation == 3:  # Bottom row + right column
            return [
                (self.x + 2, self.y), (self.x + 2, self.y + 1),  # right column
                (self.x, self.y + 2), (self.x + 1, self.y + 2), (self.x + 2, self.y + 2)  # bottom row
            ]
        return []
    
    def get_warning_zone(self):
        """Get all cells around the L-shape for warning zone"""
        warning = set()
        for cx, cy in self.cells:
            # Add all 8 neighbors
            for dx in [-1, 0, 1]:
                for dy in [-1, 0, 1]:
                    if dx == 0 and dy == 0:
                        continue
                    neighbor = (cx + dx, cy + dy)
                    if neighbor not in self.cells:
                        warning.add(neighbor)
        return warning
    
    def __repr__(self):
        return f"Wall at ({self.x}, {self.y}) rotation={self.rotation}"