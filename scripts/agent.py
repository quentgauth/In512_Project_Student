__author__ = "Aybuke Ozturk Suri, Johvany Gustave"
__copyright__ = "Copyright 2023, IN512, IPSA 2024"
__credits__ = ["Aybuke Ozturk Suri", "Johvany Gustave"]
__license__ = "Apache License 2.0"
__version__ = "1.0.0"

from network import Network
from my_constants import *

from threading import Thread
import numpy as np
from time import sleep


class Agent:
    """ Class that implements the behaviour of each agent based on their perception and communication with other agents """
    def __init__(self, server_ip):
        # State tracking for discoveries
        self.my_key_pos = None      # (x, y) of my own key
        self.my_box_pos = None      # (x, y) of my own box (treasure)
        self.has_key = False        # True when own key is found
        self.has_box = False        # True when own box is found
        self.completed = False      # True when both key and box are found
        
        # Store discoveries from other agents: {agent_id: (x, y)}
        self.other_keys = {}
        self.other_boxes = {}
        
        # Pending messages queue for broadcast processing
        self.pending_broadcasts = []

        #DO NOT TOUCH THE FOLLOWING INSTRUCTIONS
        self.network = Network(server_ip=server_ip)
        self.agent_id = self.network.id
        self.running = True
        self.network.send({"header": GET_DATA})
        self.msg = {}
        env_conf = self.network.receive()
        self.nb_agent_expected = 0
        self.nb_agent_connected = 0
        self.x, self.y = env_conf["x"], env_conf["y"]   #initial agent position
        self.w, self.h = env_conf["w"], env_conf["h"]   #environment dimensions
        cell_val = env_conf["cell_val"] #value of the cell the agent is located in
        print(f"Agent {self.agent_id} initialized at ({self.x}, {self.y}) - cell_val: {cell_val}")
        Thread(target=self.msg_cb, daemon=True).start()
        self.wait_for_connected_agent()

        
    def msg_cb(self): 
        """ Method used to handle incoming messages """
        while self.running:
            msg = self.network.receive()
            self.msg = msg
            
            if msg["header"] == MOVE:
                self.x, self.y = msg["x"], msg["y"]
            elif msg["header"] == GET_NB_AGENTS:
                self.nb_agent_expected = msg["nb_agents"]
            elif msg["header"] == GET_NB_CONNECTED_AGENTS:
                self.nb_agent_connected = msg["nb_connected_agents"]
            elif msg["header"] == BROADCAST_MSG:
                # Handle broadcast from another agent
                self._handle_broadcast(msg)
            
    def _handle_broadcast(self, msg):
        """Process broadcast messages from other agents"""
        sender = msg.get("sender")
        msg_type = msg.get("Msg type")
        position = msg.get("position")
        owner = msg.get("owner")
        
        if msg_type == KEY_DISCOVERED:
            # Another agent found a key
            if owner == self.agent_id:
                # It's MY key! Store it
                self.my_key_pos = position
                print(f"Agent {self.agent_id}: Another agent found my key at {position}!")
            else:
                # It's someone else's key
                self.other_keys[owner] = position
                print(f"Agent {self.agent_id}: Agent {sender} found key for agent {owner} at {position}")
                
        elif msg_type == BOX_DISCOVERED:
            # Another agent found a box
            if owner == self.agent_id:
                # It's MY box! Store it
                self.my_box_pos = position
                print(f"Agent {self.agent_id}: Another agent found my box at {position}!")
            else:
                # It's someone else's box
                self.other_boxes[owner] = position
                print(f"Agent {self.agent_id}: Agent {sender} found box for agent {owner} at {position}")
                
        elif msg_type == COMPLETED:
            print(f"Agent {self.agent_id}: Agent {sender} has completed their mission!")
            

    def wait_for_connected_agent(self):
        self.network.send({"header": GET_NB_AGENTS})
        check_conn_agent = True
        while check_conn_agent:
            if self.nb_agent_expected == self.nb_agent_connected:
                print("both connected!")
                check_conn_agent = False

                  

    #TODO: CREATE YOUR METHODS HERE...

            
 
if __name__ == "__main__":
    from random import randint
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("-i", "--server_ip", help="Ip address of the server", type=str, default="localhost")
    args = parser.parse_args()

    agent = Agent(args.server_ip)
    
    try:    #Manual control test0
        while True:
            cmds = {"header": int(input("0 <-> Broadcast msg\n1 <-> Get data\n2 <-> Move\n3 <-> Get nb connected agents\n4 <-> Get nb agents\n5 <-> Get item owner\n"))}
            if cmds["header"] == BROADCAST_MSG:
                cmds["Msg type"] = int(input("1 <-> Key discovered\n2 <-> Box discovered\n3 <-> Completed\n"))
                cmds["position"] = (agent.x, agent.y)
                cmds["owner"] = randint(0,3) # TODO: specify the owner of the item
            elif cmds["header"] == MOVE:
                cmds["direction"] = int(input("0 <-> Stand\n1 <-> Left\n2 <-> Right\n3 <-> Up\n4 <-> Down\n5 <-> UL\n6 <-> UR\n7 <-> DL\n8 <-> DR\n"))
            agent.network.send(cmds)
    except KeyboardInterrupt:
        pass
# it is always the same location of the agent first location



