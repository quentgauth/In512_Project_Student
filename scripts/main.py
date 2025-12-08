import sys
from server import Server
from agent import Agent
from my_constants import *
from threading import Thread
import time
import numpy as np

# Directions
OPPOSITE = {
    STAND: STAND, LEFT: RIGHT, RIGHT: LEFT, UP: DOWN, DOWN: UP,
    UP_LEFT: DOWN_RIGHT, UP_RIGHT: DOWN_LEFT, DOWN_LEFT: UP_RIGHT, DOWN_RIGHT: UP_LEFT,
}
GRADIENT_DIRS = [UP_LEFT, UP_RIGHT, DOWN_LEFT, DOWN_RIGHT, UP, DOWN, LEFT, RIGHT]


def move(agent, d):
    if agent.completed:  # Don't move if already done
        print(f"⚠️ Agent {agent.agent_id}: BLOCKED MOVE (completed)")
        return
    agent.network.send({"header": MOVE, "direction": d})
    time.sleep(0.03)


def get_data(agent):
    agent.network.send({"header": GET_DATA})
    time.sleep(0.02)
    return agent.msg


def get_item_owner(agent):
    agent.network.send({"header": GET_ITEM_OWNER})
    time.sleep(0.02)
    return agent.msg


def broadcast(agent, itype, owner, pos):
    agent.network.send({
        "header": BROADCAST_MSG,
        "Msg type": KEY_DISCOVERED if itype == KEY_TYPE else BOX_DISCOVERED,
        "position": pos, "owner": owner
    })


def move_step(agent, tx, ty):
    """One step toward target using diagonal if possible"""
    if agent.completed:  # Don't move if already done
        return False
    if agent.x == tx and agent.y == ty:
        return False
    dx, dy = tx - agent.x, ty - agent.y
    if dx > 0 and dy > 0: d = DOWN_RIGHT
    elif dx > 0 and dy < 0: d = UP_RIGHT
    elif dx < 0 and dy > 0: d = DOWN_LEFT
    elif dx < 0 and dy < 0: d = UP_LEFT
    elif dx > 0: d = RIGHT
    elif dx < 0: d = LEFT
    elif dy > 0: d = DOWN
    else: d = UP
    move(agent, d)
    return True


def move_to(agent, tx, ty):
    while agent.x != tx or agent.y != ty:
        if agent.completed:  # Stop if already done
            return
        move_step(agent, tx, ty)


def claim_known_item(agent, pos, is_key):
    """Go DIRECTLY to known item position and claim it (no gradient needed)"""
    # Don't do anything if already complete
    if agent.has_key and agent.has_box:
        return True
    
    print(f"Agent {agent.agent_id}: → Direct to {'key' if is_key else 'box'} at {pos}")
    move_to(agent, pos[0], pos[1])
    
    # Verify and claim
    val = get_data(agent).get("cell_val", 0)
    if val == 1.0:
        info = get_item_owner(agent)
        if info and info.get("owner") == agent.agent_id:
            if is_key:
                agent.has_key = True
                print(f"Agent {agent.agent_id}: ★ KEY claimed at {pos}")
            else:
                agent.has_box = True
                agent.completed = True  # STOP immediately!
                print(f"Agent {agent.agent_id}: ★ BOX claimed at {pos}")
            return True
    return False


def smart_find_item(agent, visited):
    """
    Smart item detection using triangulation:
    - val 0.5/0.6 = item is adjacent (1 step away) → check 8 neighbors ONCE
    - val 0.25/0.3 = item is 2 steps away → triangulate with 2 probes
    Returns (is_own_item, position)
    """
    # Don't search if already completed
    if agent.completed:
        return False, None
    
    val = get_data(agent).get("cell_val", 0)
    pos = (agent.x, agent.y)
    
    if val <= 0:
        return False, None
    
    # Already on item
    if val == 1.0:
        return process_item(agent, visited)
    
    # ADJACENT (0.5 or 0.6): item is 1 step away - just scan 8 neighbors once
    if val >= 0.5:
        for d in GRADIENT_DIRS:
            move(agent, d)
            if get_data(agent).get("cell_val", 0) == 1.0:
                return process_item(agent, visited)
            move(agent, OPPOSITE[d])
        return False, None
    
    # NEAR (0.25 or 0.3): item is 2 steps away - triangulate
    # Strategy: probe 2 opposite corners to find direction, then go direct
    start_x, start_y = agent.x, agent.y
    
    # Probe diagonal corners to triangulate
    probes = []
    for d in [UP_LEFT, DOWN_RIGHT]:  # Two opposite corners
        move(agent, d)
        v = get_data(agent).get("cell_val", 0)
        probes.append((d, v, agent.x, agent.y))
        move(agent, OPPOSITE[d])
    
    # Find best probe
    best = max(probes, key=lambda p: p[1])
    
    if best[1] > val:
        # Move toward the better value
        move(agent, best[0])
        
        # If now adjacent or on item, find it
        new_val = get_data(agent).get("cell_val", 0)
        if new_val == 1.0:
            return process_item(agent, visited)
        elif new_val >= 0.5:
            # Now adjacent - quick scan
            for d in GRADIENT_DIRS:
                move(agent, d)
                if get_data(agent).get("cell_val", 0) == 1.0:
                    return process_item(agent, visited)
                move(agent, OPPOSITE[d])
        elif new_val > val:
            # Keep following in same direction
            for _ in range(3):
                move(agent, best[0])
                v = get_data(agent).get("cell_val", 0)
                if v == 1.0:
                    return process_item(agent, visited)
                if v < new_val:
                    break
                new_val = v
    else:
        # Try the other diagonal pair
        for d in [UP_RIGHT, DOWN_LEFT]:
            move(agent, d)
            v = get_data(agent).get("cell_val", 0)
            if v == 1.0:
                return process_item(agent, visited)
            if v >= 0.5:
                # Adjacent - quick scan remaining
                for d2 in GRADIENT_DIRS:
                    move(agent, d2)
                    if get_data(agent).get("cell_val", 0) == 1.0:
                        return process_item(agent, visited)
                    move(agent, OPPOSITE[d2])
                return False, None
            if v > val:
                # Continue this direction
                for _ in range(2):
                    move(agent, d)
                    if get_data(agent).get("cell_val", 0) == 1.0:
                        return process_item(agent, visited)
                return False, None
            move(agent, OPPOSITE[d])
    
    return False, None


def process_item(agent, visited):
    """Process an item at current position (val == 1.0)"""
    pos = (agent.x, agent.y)
    if pos in visited:
        return False, pos
    
    info = get_item_owner(agent)
    if info and info.get("header") == GET_ITEM_OWNER:
        owner, itype = info.get("owner"), info.get("type")
        if owner is not None:
            broadcast(agent, itype, owner, pos)
            visited.add(pos)
            if owner == agent.agent_id:
                if itype == KEY_TYPE:
                    agent.my_key_pos = pos
                    agent.has_key = True
                    print(f"Agent {agent.agent_id}: ★ KEY at {pos}")
                    return True, pos
                else:  # BOX_TYPE
                    agent.my_box_pos = pos
                    # Only claim box if we have the key!
                    if agent.has_key:
                        agent.has_box = True
                        agent.completed = True
                        print(f"Agent {agent.agent_id}: ★ BOX at {pos}")
                        return True, pos
                    else:
                        # Found our box but don't have key - remember position and go get key
                        print(f"Agent {agent.agent_id}: Found my BOX at {pos} but need KEY first!")
                        return False, pos  # Continue to find key
            print(f"Agent {agent.agent_id}: Item for {owner} at {pos}")
            return False, pos
    return False, None


def near_visited(agent, visited):
    """Check if we're near a visited item or a known item of another agent"""
    # Check visited set
    for vx, vy in visited:
        if abs(agent.x - vx) <= 2 and abs(agent.y - vy) <= 2:
            return True
    
    # Check known items of other agents (skip their halos)
    for owner, pos in agent.other_keys.items():
        if pos and abs(agent.x - pos[0]) <= 2 and abs(agent.y - pos[1]) <= 2:
            return True
    for owner, pos in agent.other_boxes.items():
        if pos and abs(agent.x - pos[0]) <= 2 and abs(agent.y - pos[1]) <= 2:
            return True
    
    return False


def check_known_items(agent):
    """Check if we know where our items are and go get them directly.
    Returns True if mission complete (has both key and box)."""
    # Priority 1: Get key if we know where it is
    if not agent.has_key and agent.my_key_pos:
        claim_known_item(agent, agent.my_key_pos, is_key=True)
    
    # Priority 2: Get box if we have key and know where box is
    if agent.has_key and not agent.has_box and agent.my_box_pos:
        claim_known_item(agent, agent.my_box_pos, is_key=False)
    
    # Return True if mission complete
    return agent.has_key and agent.has_box


def get_zone_for_agent(agent_id, nb_agents, W, H):
    """
    Divide map into zones based on number of agents.
    Returns (x_start, x_end, y_start, y_end) for this agent's zone.
    """
    OVERLAP = 2  # Overlap between zones to not miss items at boundaries
    
    if nb_agents == 1:
        # Single agent: explore full map
        return 0, W, 0, H
    
    elif nb_agents == 2:
        # 2 agents: left/right split
        if agent_id == 0:
            return 0, W // 2 + OVERLAP, 0, H
        else:
            return W // 2 - OVERLAP, W, 0, H
    
    else:  # 3 or 4 agents: quadrant split
        # Agent 0: top-left, Agent 1: top-right
        # Agent 2: bottom-left, Agent 3: bottom-right
        mid_x, mid_y = W // 2, H // 2
        
        if agent_id == 0:
            return 0, mid_x + OVERLAP, 0, mid_y + OVERLAP
        elif agent_id == 1:
            return mid_x - OVERLAP, W, 0, mid_y + OVERLAP
        elif agent_id == 2:
            return 0, mid_x + OVERLAP, mid_y - OVERLAP, H
        else:  # agent_id == 3
            return mid_x - OVERLAP, W, mid_y - OVERLAP, H


def sweep_zone(agent, visited, x_start, x_end, y_start, y_end, STEP):
    """Sweep a specific zone of the map"""
    going_right = (agent.agent_id % 2 == 0)  # Alternate start direction
    y = y_start
    
    while y < y_end:
        if check_known_items(agent):
            return True
        
        if going_right:
            x_range = range(x_start, x_end, STEP)
        else:
            x_range = range(min(x_end - 1, agent.w - 1), x_start - 1, -STEP)
        
        for x in x_range:
            if check_known_items(agent):
                return True
            
            x = max(0, min(x, agent.w - 1))
            target_y = max(0, min(y, agent.h - 1))
            
            while agent.x != x or agent.y != target_y:
                move_step(agent, x, target_y)
                val = get_data(agent).get("cell_val", 0)
                
                if val > 0 and val < 1.0 and not near_visited(agent, visited):
                    smart_find_item(agent, visited)
                    if check_known_items(agent):
                        return True
            
            val = get_data(agent).get("cell_val", 0)
            if val > 0 and not near_visited(agent, visited):
                smart_find_item(agent, visited)
            
            if agent.has_key and agent.has_box:
                return True
        
        y += STEP
        going_right = not going_right
    
    return False


def optimal_sweep(agent, visited):
    """
    Optimal sweep strategy for 1-4 agents with dynamic zone adaptation.
    When an agent finishes its zone, it explores zones of completed agents.
    """
    W, H = agent.w, agent.h
    STEP = 4
    nb_agents = agent.nb_agent_expected
    
    # Check known items first
    if check_known_items(agent):
        return
    
    # Get this agent's primary zone
    x1, x2, y1, y2 = get_zone_for_agent(agent.agent_id, nb_agents, W, H)
    print(f"Agent {agent.agent_id}: Sweeping zone ({x1},{y1}) to ({x2},{y2})")
    
    # Sweep primary zone
    if sweep_zone(agent, visited, x1, x2, y1, y2, STEP):
        return
    
    if agent.has_key and agent.has_box:
        return
    
    # Smart fallback: explore zones of OTHER agents
    # Priority: agents who have completed (we know both their key and box)
    for other_id in range(nb_agents):
        if other_id == agent.agent_id:
            continue
        
        if check_known_items(agent):
            return
        
        # Get other agent's zone
        ox1, ox2, oy1, oy2 = get_zone_for_agent(other_id, nb_agents, W, H)
        
        # Check if we've likely covered this zone (if we know the other's items)
        other_key_known = other_id in agent.other_keys
        other_box_known = other_id in agent.other_boxes
        
        # If we already know the other's items, their zone might still have our items
        if not (agent.has_key and agent.has_box):
            print(f"Agent {agent.agent_id}: Exploring Agent {other_id}'s zone ({ox1},{oy1}) to ({ox2},{oy2})")
            if sweep_zone(agent, visited, ox1, ox2, oy1, oy2, STEP):
                return
    
    # Final fallback: full map sweep
    if not (agent.has_key and agent.has_box):
        print(f"Agent {agent.agent_id}: Full map sweep...")
        sweep_zone(agent, visited, 0, W, 0, H, STEP)


def agent_loop(agent):
    print(f"Agent {agent.agent_id}: Start ({agent.x}, {agent.y})")
    visited = set()
    
    try:
        while not agent.completed:
            optimal_sweep(agent, visited)
            
            if agent.has_key and agent.has_box:
                agent.completed = True
                agent.network.send({
                    "header": BROADCAST_MSG, "Msg type": COMPLETED,
                    "position": (agent.x, agent.y), "owner": agent.agent_id
                })
                print(f"Agent {agent.agent_id}: ═══ DONE ═══")
                break
            
            time.sleep(0.1)
    except Exception as e:
        import traceback
        print(f"Agent {agent.agent_id}: Error: {e}")
        traceback.print_exc()


if __name__ == "__main__":
    import sys
    
    print("Starting agents...")
    
    # Create first agent
    agents = [Agent("localhost")]
    
    # Wait until we know how many agents are expected
    while agents[0].nb_agent_expected == 0:
        time.sleep(0.1)
    
    nb_expected = agents[0].nb_agent_expected
    print(f"Server expects {nb_expected} agents")
    
    # Create remaining agents
    for i in range(1, nb_expected):
        agents.append(Agent("localhost"))
    
    print(f"Created {len(agents)} agents | Map: {agents[0].w}x{agents[0].h}")
    for a in agents:
        print(f"  Agent {a.agent_id} at ({a.x}, {a.y})")
    
    # Start all agent threads
    threads = []
    for agent in agents:
        t = Thread(target=agent_loop, args=(agent,), daemon=True)
        threads.append(t)
        t.start()
    
    # Wait for all agents to complete
    try:
        while not all(a.completed for a in agents):
            time.sleep(1)
            status = " | ".join(
                "✓" if a.completed else ("🔑" if a.has_key else "...")
                for a in agents
            )
            print(f"[{status}]")
    except KeyboardInterrupt:
        print("Stopped")
    
    print("=== ALL DONE ===")

