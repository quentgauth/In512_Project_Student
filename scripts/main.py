import sys
from server import Server
from agent import Agent
from my_constants import *
from threading import Thread
import time
import random
import numpy as np

# Directions
OPPOSITE = {
    STAND: STAND, LEFT: RIGHT, RIGHT: LEFT, UP: DOWN, DOWN: UP,
    UP_LEFT: DOWN_RIGHT, UP_RIGHT: DOWN_LEFT, DOWN_LEFT: UP_RIGHT, DOWN_RIGHT: UP_LEFT,
}
GRADIENT_DIRS = [UP_LEFT, UP_RIGHT, DOWN_LEFT, DOWN_RIGHT, UP, DOWN, LEFT, RIGHT]

# Global game over flag
game_over_flag = False


def move(agent, d):
    global game_over_flag
    if agent.completed or game_over_flag:  # Don't move if already done or game over
        return
    agent.network.send({"header": MOVE, "direction": d})
    time.sleep(0.03)
    
    # Check if server responded with game over
    if agent.msg and agent.msg.get("game_over"):
        game_over_flag = True
        print(f"💀 Agent {agent.agent_id}: Game Over detected!")
        agent.completed = True


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


def get_direction_from_delta(dx, dy):
    """Convert delta (dx, dy) to a direction constant"""
    if dx == 0 and dy == 0: return STAND
    if dx == 1 and dy == 0: return RIGHT
    if dx == -1 and dy == 0: return LEFT
    if dx == 0 and dy == 1: return DOWN
    if dx == 0 and dy == -1: return UP
    if dx == 1 and dy == 1: return DOWN_RIGHT
    if dx == 1 and dy == -1: return UP_RIGHT
    if dx == -1 and dy == 1: return DOWN_LEFT
    if dx == -1 and dy == -1: return UP_LEFT
    return STAND


def get_perpendicular_dirs(direction):
    """Get perpendicular directions for a given direction"""
    horizontal = [LEFT, RIGHT]
    vertical = [UP, DOWN]
    
    if direction in [LEFT, RIGHT]:
        return vertical
    elif direction in [UP, DOWN]:
        return horizontal
    elif direction in [UP_LEFT, UP_RIGHT]:
        return [DOWN, LEFT, RIGHT]
    elif direction in [DOWN_LEFT, DOWN_RIGHT]:
        return [UP, LEFT, RIGHT]
    return horizontal + vertical





def check_wall_danger(val):
    """Check if value represents a wall warning zone (0.35)"""
    return abs(val - 0.35) < 0.01


def is_in_bounds(agent, pos):
    """Check if position is within map bounds"""
    return 0 <= pos[0] < agent.w and 0 <= pos[1] < agent.h


def rotate_direction(d, clockwise=True):
    """Rotate direction by 45 degrees (one step in cardinal/diagonal order)"""
    order = [UP, UP_RIGHT, RIGHT, DOWN_RIGHT, DOWN, DOWN_LEFT, LEFT, UP_LEFT]
    if d not in order:
        return UP
    idx = order.index(d)
    step = 1 if clockwise else -1
    return order[(idx + step) % 8]


def is_path_clear(agent, tx, ty):
    """Check if we can see the target (simple distance check)"""
    dist = abs(tx - agent.x) + abs(ty - agent.y)
    return dist > 0


def scan_surroundings(agent, quick=False):
    """
    Probe adjacent cells to detect wall warning zones (0.35).
    Returns dict of {direction: (is_safe, cell_value)}
    """
    surroundings = {}
    
    if quick:
        return surroundings
    
    # Check each direction by probing
    for d in GRADIENT_DIRS:
        target = get_target_from_direction(agent.x, agent.y, d)
        
        # Out of bounds
        if not is_in_bounds(agent, target):
            surroundings[d] = (False, 1.0)
            continue
        
        # Probe by moving and immediately checking
        old_x, old_y = agent.x, agent.y
        move(agent, d)
        
        if agent.x != old_x or agent.y != old_y:
            # Successfully moved - check value
            probe_data = get_data(agent)
            val = probe_data.get("cell_val", 0) if probe_data else 0
            
            if check_wall_danger(val) or val == 1.0:
                # Danger zone - retreat
                surroundings[d] = (False, val)
                move(agent, OPPOSITE[d])  # Retreat immediately
            else:
                # Safe - return to original position
                surroundings[d] = (True, val)
                move(agent, OPPOSITE[d])
        else:
            # Couldn't move - blocked
            surroundings[d] = (False, 1.0)
    
    return surroundings


def is_in_l_corner(agent):
    """
    Detect if we're trapped by testing actual movement.
    Returns (is_trapped, list_of_safe_directions)
    """
    blocked_count = 0
    safe_dirs = []
    
    # Check all 8 directions by trying to probe
    for d in GRADIENT_DIRS:
        target = get_target_from_direction(agent.x, agent.y, d)
        
        if not is_in_bounds(agent, target):
            blocked_count += 1
        else:
            # Try to move and check if safe
            old_pos = (agent.x, agent.y)
            move(agent, d)
            if agent.x != old_pos[0] or agent.y != old_pos[1]:
                # We moved - check if safe
                data = get_data(agent)
                val = data.get("cell_val", 0) if data else 0
                if check_wall_danger(val):
                    blocked_count += 1
                else:
                    safe_dirs.append(d)
                # Return to original position
                move(agent, OPPOSITE[d])
            else:
                blocked_count += 1
    
    # Trapped if 5+ directions are blocked
    is_trapped = blocked_count >= 5
    return is_trapped, safe_dirs



def retreat_and_slide(agent, previous_pos):
    """
    Safe escape from danger zone (0.35).
    STRATEGY: RETREAT FIRST, THEN SLIDE.
    """
    current_x, current_y = agent.x, agent.y
    
    # 1. RETREAT to safety
    back_d = get_direction_from_delta(previous_pos[0] - current_x, previous_pos[1] - current_y)
    move(agent, back_d)
    
    # Check if we successfully retreated
    if agent.x == current_x and agent.y == current_y:
         print(f"Agent {agent.agent_id}: 🚨 Critical! Failed to retreat from ({agent.x}, {agent.y})")
         return False
         
    # From safe position, try to slide around the danger
    danger_pos = (current_x, current_y)
    all_dirs = [UP_LEFT, UP_RIGHT, DOWN_LEFT, DOWN_RIGHT, UP, DOWN, LEFT, RIGHT]
    
    for d in all_dirs:
        nx, ny = get_target_from_direction(agent.x, agent.y, d)
        
        # Don't go back to the danger spot
        if nx == danger_pos[0] and ny == danger_pos[1]: 
            continue
        
        # Check bounds
        if not is_in_bounds(agent, (nx, ny)): 
            continue
        
        # Move and check
        old_pos = (agent.x, agent.y)
        move(agent, d)
        if agent.x == nx and agent.y == ny:
             # Moved successfully. Check safety.
             data = get_data(agent)
             val = data.get("cell_val", 0) if data else 0
             if check_wall_danger(val):
                  # Still danger - retreat
                  move(agent, OPPOSITE[d])
                  continue
             else:
                  # Safe!
                  print(f"Agent {agent.agent_id}: 🦶 Slid to ({nx}, {ny})")
                  return True

    print(f"Agent {agent.agent_id}: Could not slide safely. Staying at ({agent.x}, {agent.y})")
    return False





def contour_around_wall(agent, target_x, target_y, previous_pos):
    """
    Smart L-shaped wall bypass algorithm.
    Strategy: Move perpendicular to wall until clear, then resume toward target.
    """
    global game_over_flag
    
    if game_over_flag:
        return False
        
    print(f"Agent {agent.agent_id}: 🚧 Wall detected at ({agent.x}, {agent.y})! Initiating safe contour...")
    
    start_pos = (agent.x, agent.y)
    
    # 1. RETREAT if on danger zone
    data = get_data(agent)
    if data and check_wall_danger(data.get("cell_val", 0)):
        print(f"Agent {agent.agent_id}: 🔙 On danger zone, retreating...")
        if previous_pos != (agent.x, agent.y):
            back_d = get_direction_from_delta(previous_pos[0] - agent.x, previous_pos[1] - agent.y)
            move(agent, back_d)
    
    # 2. SCAN to find safe directions
    print(f"Agent {agent.agent_id}: 🔍 Scanning surroundings...")
    surroundings = scan_surroundings(agent)
    
    # 3. Identify which direction is blocked (toward target)
    dx = target_x - agent.x
    dy = target_y - agent.y
    
    # 4. CHECK IF TRAPPED
    is_trapped, safe_dirs = is_in_l_corner(agent)
    if is_trapped:
        diagonals_first = sorted(safe_dirs, key=lambda d: d in [UP_LEFT, UP_RIGHT, DOWN_LEFT, DOWN_RIGHT], reverse=True)
        print(f"Agent {agent.agent_id}: 🪤 Trapped! Safe directions: {diagonals_first}")
        if diagonals_first:
            for escape_dir in diagonals_first:
                old_pos = (agent.x, agent.y)
                move(agent, escape_dir)
                if agent.x != old_pos[0] or agent.y != old_pos[1]:
                    escape_data = get_data(agent)
                    if escape_data and not check_wall_danger(escape_data.get("cell_val", 0)):
                        print(f"Agent {agent.agent_id}: ✅ Escaped via {escape_dir}")
                        return True
                    else:
                        move(agent, OPPOSITE[escape_dir])
            return False
        else:
            print(f"Agent {agent.agent_id}: 🔓 Attempting forced escape...")
            for force_dir in [DOWN, UP, LEFT, RIGHT, DOWN_LEFT, DOWN_RIGHT, UP_LEFT, UP_RIGHT]:
                target_pos = get_target_from_direction(agent.x, agent.y, force_dir)
                if not is_in_bounds(agent, target_pos):
                    continue
                old_pos = (agent.x, agent.y)
                move(agent, force_dir)
                if agent.x != old_pos[0] or agent.y != old_pos[1]:
                    force_data = get_data(agent)
                    force_val = force_data.get("cell_val", 0) if force_data else 0
                    if not check_wall_danger(force_val):
                        print(f"Agent {agent.agent_id}: ✅ Forced escape via {force_dir}")
                        return True
                    else:
                        move(agent, OPPOSITE[force_dir])
            print(f"Agent {agent.agent_id}: 💀 Forced escape failed!")
            return False
    
    # 5. L-SHAPED BYPASS STRATEGY
    # Move perpendicular to the blocked direction for at least MIN_BYPASS_STEPS
    # before trying to resume toward target
    
    MIN_BYPASS_STEPS = 5  # Must move at least this many steps perpendicular
    MAX_BYPASS_STEPS = 20  # Give up after this many steps
    
    # Determine perpendicular directions based on target direction
    if abs(dx) >= abs(dy):  # Mostly horizontal movement blocked
        # Try vertical bypass
        if agent.y < agent.h // 2:
            primary_bypass = DOWN
            secondary_bypass = UP
        else:
            primary_bypass = UP
            secondary_bypass = DOWN
    else:  # Mostly vertical movement blocked
        # Try horizontal bypass
        if agent.x < agent.w // 2:
            primary_bypass = RIGHT
            secondary_bypass = LEFT
        else:
            primary_bypass = LEFT
            secondary_bypass = RIGHT
    
    # Try primary bypass direction first, then secondary
    for bypass_dir in [primary_bypass, secondary_bypass]:
        if game_over_flag or agent.completed:
            return False
        
        bypass_count = 0
        bypass_start = (agent.x, agent.y)
        
        print(f"Agent {agent.agent_id}: 🔄 Trying bypass direction {bypass_dir}")
        
        # Phase 1: Move perpendicular to get clear of the wall
        for step in range(MAX_BYPASS_STEPS):
            if game_over_flag or agent.completed:
                return False
            
            old_pos = (agent.x, agent.y)
            move(agent, bypass_dir)
            
            if agent.x == old_pos[0] and agent.y == old_pos[1]:
                # Blocked in bypass direction, try rotating slightly
                alt_dirs = [rotate_direction(bypass_dir, True), rotate_direction(bypass_dir, False)]
                moved = False
                for alt in alt_dirs:
                    target_pos = get_target_from_direction(agent.x, agent.y, alt)
                    if is_in_bounds(agent, target_pos):
                        move(agent, alt)
                        if agent.x != old_pos[0] or agent.y != old_pos[1]:
                            # Check safety
                            alt_data = get_data(agent)
                            if alt_data and check_wall_danger(alt_data.get("cell_val", 0)):
                                move(agent, OPPOSITE[alt])
                            else:
                                moved = True
                                bypass_count += 1
                                break
                if not moved:
                    break  # Can't bypass in this direction
            else:
                # Moved! Check if safe
                bypass_data = get_data(agent)
                bypass_val = bypass_data.get("cell_val", 0) if bypass_data else 0
                
                if check_wall_danger(bypass_val):
                    # Hit wall during bypass, retreat and try different angle
                    move(agent, OPPOSITE[bypass_dir])
                    break
                
                bypass_count += 1
            
            # After minimum bypass, try heading toward target
            if bypass_count >= MIN_BYPASS_STEPS:
                # Try one step toward target
                tgt_dir = get_direction_from_delta(
                    1 if target_x > agent.x else (-1 if target_x < agent.x else 0),
                    1 if target_y > agent.y else (-1 if target_y < agent.y else 0)
                )
                
                tgt_pos = get_target_from_direction(agent.x, agent.y, tgt_dir)
                if is_in_bounds(agent, tgt_pos):
                    test_old = (agent.x, agent.y)
                    move(agent, tgt_dir)
                    if agent.x != test_old[0] or agent.y != test_old[1]:
                        test_data = get_data(agent)
                        if test_data and not check_wall_danger(test_data.get("cell_val", 0)):
                            # Successfully bypassed and can head toward target!
                            print(f"Agent {agent.agent_id}: ✅ Bypass successful after {bypass_count} steps!")
                            return True
                        else:
                            # Still blocked, retreat and continue bypass
                            move(agent, OPPOSITE[tgt_dir])
        
        # If we moved at least some, consider it partial success
        if bypass_count >= 2:
            new_dist = abs(target_x - agent.x) + abs(target_y - agent.y)
            old_dist = abs(target_x - bypass_start[0]) + abs(target_y - bypass_start[1])
            if new_dist < old_dist:
                print(f"Agent {agent.agent_id}: ✅ Made progress via bypass!")
                return True
    
    print(f"Agent {agent.agent_id}: ❌ Bypass exhausted all options")
    return False


def move_step(agent, tx, ty):
    """
    One step toward target with wall avoidance.
    Uses real-time wall detection.
    """
    global game_over_flag
    if agent.completed or game_over_flag:
        return False
    
    old_x, old_y = agent.x, agent.y
    dx, dy = tx - agent.x, ty - agent.y
    
    if dx == 0 and dy == 0: 
        return False
    
    # PRIORITIZE DIAGONAL when both dx and dy are non-zero
    d_diagonal = STAND
    if dx > 0 and dy > 0: d_diagonal = DOWN_RIGHT
    elif dx > 0 and dy < 0: d_diagonal = UP_RIGHT
    elif dx < 0 and dy > 0: d_diagonal = DOWN_LEFT
    elif dx < 0 and dy < 0: d_diagonal = UP_LEFT
    
    # Cardinal directions as fallback
    d_horizontal = RIGHT if dx > 0 else LEFT if dx < 0 else STAND
    d_vertical = DOWN if dy > 0 else UP if dy < 0 else STAND
    
    # Build list: DIAGONAL FIRST, then cardinals
    directions_to_try = []
    if d_diagonal != STAND:
        directions_to_try.append(d_diagonal)
    if d_horizontal != STAND:
        directions_to_try.append(d_horizontal)
    if d_vertical != STAND:
        directions_to_try.append(d_vertical)
    
    for direction in directions_to_try:
        target_pos = get_target_from_direction(agent.x, agent.y, direction)
        
        if not is_in_bounds(agent, target_pos):
            continue
        
        # Try to move
        move(agent, direction)
        
        if agent.x != old_x or agent.y != old_y:
            # Moved successfully - check if safe
            data = get_data(agent)
            val = data.get("cell_val", 0) if data else 0
            
            if check_wall_danger(val):
                # DANGER! Retreat
                move(agent, OPPOSITE[direction])
                continue
            
            return True  # Successfully moved to safe cell
    
    # All directions failed
    return False


def get_target_from_direction(x, y, d):
    """Get target position from current position and direction"""
    deltas = {
        STAND: (0, 0), LEFT: (-1, 0), RIGHT: (1, 0), UP: (0, -1), DOWN: (0, 1),
        UP_LEFT: (-1, -1), UP_RIGHT: (1, -1), DOWN_LEFT: (-1, 1), DOWN_RIGHT: (1, 1)
    }
    dx, dy = deltas.get(d, (0, 0))
    return (x + dx, y + dy)


def init_agent_memory(agent):
    """Initialize path memory for an agent if not already done."""
    if not hasattr(agent, 'blocked_zones'):
        agent.blocked_zones = set()  # Positions where we got stuck
    if not hasattr(agent, 'failed_bypasses'):
        agent.failed_bypasses = {}  # {(pos, target): set of failed directions}
    if not hasattr(agent, 'path_memory'):
        agent.path_memory = {}  # {target: list of positions tried}


def get_bypass_direction(agent, target_dir, current_pos, target_pos, attempt_num=0):
    """
    Get a systematic bypass direction based on the target direction.
    Uses memory to avoid repeating failed bypass attempts.
    Returns a tuple (primary_bypass, secondary_bypass) for perpendicular movement.
    """
    init_agent_memory(agent)
    
    # Get failed directions for this position+target combo
    key = (current_pos, target_pos)
    failed_dirs = agent.failed_bypasses.get(key, set())
    
    # All possible bypass directions in order of preference
    all_bypass_options = []
    
    # Map target direction to perpendicular bypass options
    if target_dir in [LEFT, RIGHT]:
        all_bypass_options = [DOWN, UP, DOWN_LEFT, DOWN_RIGHT, UP_LEFT, UP_RIGHT]
    elif target_dir in [UP, DOWN]:
        all_bypass_options = [RIGHT, LEFT, UP_RIGHT, DOWN_RIGHT, UP_LEFT, DOWN_LEFT]
    elif target_dir in [UP_LEFT, DOWN_RIGHT]:
        all_bypass_options = [UP_RIGHT, DOWN_LEFT, UP, RIGHT, DOWN, LEFT]
    elif target_dir in [UP_RIGHT, DOWN_LEFT]:
        all_bypass_options = [UP_LEFT, DOWN_RIGHT, UP, LEFT, DOWN, RIGHT]
    else:
        all_bypass_options = [DOWN, UP, LEFT, RIGHT, DOWN_LEFT, DOWN_RIGHT, UP_LEFT, UP_RIGHT]
    
    # Choose based on position on map (prefer moving toward center)
    if agent.y < agent.h // 2:
        # Upper half, prefer DOWN
        all_bypass_options = sorted(all_bypass_options, key=lambda d: d not in [DOWN, DOWN_LEFT, DOWN_RIGHT])
    else:
        # Lower half, prefer UP
        all_bypass_options = sorted(all_bypass_options, key=lambda d: d not in [UP, UP_LEFT, UP_RIGHT])
    
    if agent.x < agent.w // 2:
        # Left half, prefer RIGHT as secondary
        pass
    else:
        # Right half, prefer LEFT as secondary
        all_bypass_options = sorted(all_bypass_options, key=lambda d: d in [RIGHT, UP_RIGHT, DOWN_RIGHT])
    
    # Filter out failed directions
    available = [d for d in all_bypass_options if d not in failed_dirs]
    
    # If we've tried everything, reset and try again with rotation
    if len(available) < 2:
        # Rotate preferences based on attempt number
        rotation = attempt_num % len(all_bypass_options)
        available = all_bypass_options[rotation:] + all_bypass_options[:rotation]
    
    if len(available) >= 2:
        return available[0], available[1]
    elif len(available) == 1:
        return available[0], all_bypass_options[0]
    else:
        return DOWN, UP


def systematic_bypass(agent, tx, ty, previous_pos, initial_direction, attempt_num=0):
    """
    Systematic bypass strategy with memory.
    Remembers which bypass directions failed and tries different ones.
    """
    global game_over_flag
    
    if game_over_flag or agent.completed:
        return False
    
    init_agent_memory(agent)
    
    MAX_BYPASS_STEPS = 15
    MIN_BYPASS_BEFORE_RETRY = 3
    
    current_pos = (agent.x, agent.y)
    target_pos = (tx, ty)
    key = (current_pos, target_pos)
    
    # Mark this position as potentially blocked
    agent.blocked_zones.add(current_pos)
    
    # Get bypass directions, considering previously failed attempts
    primary_bypass, secondary_bypass = get_bypass_direction(
        agent, initial_direction, current_pos, target_pos, attempt_num
    )
    
    for bypass_dir in [primary_bypass, secondary_bypass]:
        if game_over_flag or agent.completed:
            return False
        
        bypass_steps = 0
        start_pos = (agent.x, agent.y)
        path_taken = [start_pos]
        
        print(f"Agent {agent.agent_id}: 🔄 Trying bypass dir {bypass_dir} (attempt {attempt_num})")
        
        for step in range(MAX_BYPASS_STEPS):
            if game_over_flag or agent.completed:
                return False
            
            # Check if current position is in blocked zones (avoid returning to bad spots)
            if (agent.x, agent.y) in agent.blocked_zones and (agent.x, agent.y) != start_pos:
                # We've been here before and it was bad, try to escape differently
                print(f"Agent {agent.agent_id}: ⚠️ Avoiding known blocked zone at ({agent.x}, {agent.y})")
                break
            
            # After minimum bypass steps, try resuming toward target
            if bypass_steps >= MIN_BYPASS_BEFORE_RETRY:
                dx = tx - agent.x
                dy = ty - agent.y
                resume_dir = get_direction_from_delta(
                    1 if dx > 0 else (-1 if dx < 0 else 0),
                    1 if dy > 0 else (-1 if dy < 0 else 0)
                )
                
                if resume_dir != STAND:
                    resume_pos = get_target_from_direction(agent.x, agent.y, resume_dir)
                    # Check if resume position is in blocked zones
                    if resume_pos not in agent.blocked_zones and is_in_bounds(agent, resume_pos):
                        old = (agent.x, agent.y)
                        move(agent, resume_dir)
                        if agent.x != old[0] or agent.y != old[1]:
                            resume_data = get_data(agent)
                            if resume_data and not check_wall_danger(resume_data.get("cell_val", 0)):
                                print(f"Agent {agent.agent_id}: ✅ Bypass OK after {bypass_steps} steps")
                                # Clear this position from blocked zones since we found a way
                                agent.blocked_zones.discard(start_pos)
                                return True
                            else:
                                # Still blocked, mark and retreat
                                agent.blocked_zones.add((agent.x, agent.y))
                                move(agent, OPPOSITE[resume_dir])
            
            # Continue bypass movement
            bypass_pos = get_target_from_direction(agent.x, agent.y, bypass_dir)
            
            # Skip if out of bounds or known blocked
            if not is_in_bounds(agent, bypass_pos):
                break
            if bypass_pos in agent.blocked_zones:
                # Try rotating direction
                alt_dirs = [rotate_direction(bypass_dir, True), rotate_direction(bypass_dir, False)]
                found_alt = False
                for alt in alt_dirs:
                    alt_pos = get_target_from_direction(agent.x, agent.y, alt)
                    if is_in_bounds(agent, alt_pos) and alt_pos not in agent.blocked_zones:
                        bypass_dir = alt
                        found_alt = True
                        break
                if not found_alt:
                    break
            
            old = (agent.x, agent.y)
            move(agent, bypass_dir)
            
            if agent.x == old[0] and agent.y == old[1]:
                # Can't move, try rotating
                alt_dirs = [rotate_direction(bypass_dir, True), rotate_direction(bypass_dir, False)]
                moved = False
                for alt in alt_dirs:
                    alt_pos = get_target_from_direction(agent.x, agent.y, alt)
                    if is_in_bounds(agent, alt_pos) and alt_pos not in agent.blocked_zones:
                        move(agent, alt)
                        if agent.x != old[0] or agent.y != old[1]:
                            alt_data = get_data(agent)
                            if alt_data and not check_wall_danger(alt_data.get("cell_val", 0)):
                                bypass_steps += 1
                                path_taken.append((agent.x, agent.y))
                                moved = True
                                break
                            else:
                                agent.blocked_zones.add((agent.x, agent.y))
                                move(agent, OPPOSITE[alt])
                if not moved:
                    break
            else:
                # Check if safe
                bypass_data = get_data(agent)
                if bypass_data and check_wall_danger(bypass_data.get("cell_val", 0)):
                    agent.blocked_zones.add((agent.x, agent.y))
                    move(agent, OPPOSITE[bypass_dir])
                    break
                bypass_steps += 1
                path_taken.append((agent.x, agent.y))
        
        # Check if we made progress
        if bypass_steps > 0:
            new_dist = abs(tx - agent.x) + abs(ty - agent.y)
            old_dist = abs(tx - start_pos[0]) + abs(ty - start_pos[1])
            if new_dist < old_dist:
                print(f"Agent {agent.agent_id}: ↪️ Progress! ({bypass_steps} steps, dist {old_dist}->{new_dist})")
                return True
            elif agent.x != start_pos[0] or agent.y != start_pos[1]:
                # We moved but didn't get closer - mark this direction as failed
                if key not in agent.failed_bypasses:
                    agent.failed_bypasses[key] = set()
                agent.failed_bypasses[key].add(bypass_dir)
                print(f"Agent {agent.agent_id}: ⚠️ No progress with dir {bypass_dir}, will try different next time")
        else:
            # Complete failure for this direction
            if key not in agent.failed_bypasses:
                agent.failed_bypasses[key] = set()
            agent.failed_bypasses[key].add(bypass_dir)
    
    print(f"Agent {agent.agent_id}: ❌ Bypass exhausted (attempt {attempt_num})")
    return False


def move_to(agent, tx, ty):
    """
    Move to target with wall avoidance.
    Uses path memory to avoid repeating failed routes.
    """
    global game_over_flag
    
    init_agent_memory(agent)
    
    max_attempts = (agent.w + agent.h) * 2
    attempts = 0
    stuck_count = 0
    contour_count = 0
    bypass_attempt = 0  # Track how many different bypass strategies we've tried
    previous_pos = (agent.x, agent.y)
    recent_positions = []
    
    # Calculate initial direction toward target
    initial_dx = tx - agent.x
    initial_dy = ty - agent.y
    initial_direction = get_direction_from_delta(
        1 if initial_dx > 0 else (-1 if initial_dx < 0 else 0),
        1 if initial_dy > 0 else (-1 if initial_dy < 0 else 0)
    )
    
    while agent.x != tx or agent.y != ty:
        if agent.completed or game_over_flag:
            return
        
        current_pos = (agent.x, agent.y)
        
        # LOOP DETECTION with memory-based escape
        if current_pos in recent_positions[-10:] if len(recent_positions) > 10 else current_pos in recent_positions:
            loop_count = recent_positions.count(current_pos) + 1
            if loop_count >= 3:
                bypass_attempt += 1
                print(f"Agent {agent.agent_id}: 🔁 Loop at {current_pos} (bypass attempt #{bypass_attempt})")
                
                # Mark this position as trouble spot
                agent.blocked_zones.add(current_pos)
                
                # Try systematic bypass with increasing attempt number
                if systematic_bypass(agent, tx, ty, previous_pos, initial_direction, bypass_attempt):
                    recent_positions.clear()
                else:
                    attempts += 5
                    # If we've tried many times, give up on this exact path
                    if bypass_attempt >= 5:
                        print(f"Agent {agent.agent_id}: ⏹️ Too many bypass failures, abandoning target ({tx}, {ty})")
                        return
                continue
        
        recent_positions.append(current_pos)
        if len(recent_positions) > 50:
            recent_positions.pop(0)
        
        old_x, old_y = agent.x, agent.y
        
        # Check if next step toward target is in blocked zones
        dx = tx - agent.x
        dy = ty - agent.y
        next_dir = get_direction_from_delta(
            1 if dx > 0 else (-1 if dx < 0 else 0),
            1 if dy > 0 else (-1 if dy < 0 else 0)
        )
        next_pos = get_target_from_direction(agent.x, agent.y, next_dir)
        
        if next_pos in agent.blocked_zones:
            # Direct path blocked, use bypass immediately
            bypass_attempt += 1
            if systematic_bypass(agent, tx, ty, previous_pos, initial_direction, bypass_attempt):
                continue
        
        # Try to move one step
        move_result = move_step(agent, tx, ty)
        
        # Check for wall warning zone
        data = get_data(agent)
        if data:
            val = data.get("cell_val", 0)
            if check_wall_danger(val):
                # Mark this as blocked
                agent.blocked_zones.add((agent.x, agent.y))
                contour_count += 1
                if contour_count > 10:
                    print(f"Agent {agent.agent_id}: ⏹️ Too many contours, giving up on target ({tx}, {ty})")
                    return
                print(f"Agent {agent.agent_id}: 🚧 Danger zone, contour...")
                contour_around_wall(agent, tx, ty, previous_pos)
                stuck_count = 0
                continue
        
        if agent.x == old_x and agent.y == old_y:
            stuck_count += 1
            attempts += 1
            
            if stuck_count > 3:
                bypass_attempt += 1
                contour_count += 1
                if contour_count > 10:
                    print(f"Agent {agent.agent_id}: ⏹️ Too many contours, giving up on target ({tx}, {ty})")
                    return
                print(f"Agent {agent.agent_id}: 🔄 Stuck, bypass attempt #{bypass_attempt}...")
                if systematic_bypass(agent, tx, ty, previous_pos, initial_direction, bypass_attempt):
                    stuck_count = 0
                else:
                    contour_around_wall(agent, tx, ty, previous_pos)
                    stuck_count = 0
            
            if attempts > max_attempts:
                print(f"Agent {agent.agent_id}: ⏹️ Max attempts reached for target ({tx}, {ty})")
                return
        else:
            stuck_count = 0
            attempts += 1
            previous_pos = (old_x, old_y)


def claim_known_item(agent, pos, is_key):
    """Go DIRECTLY to known item position and claim it"""
    global game_over_flag
    
    # Don't do anything if already complete or game over
    if agent.has_key and agent.has_box:
        return True
    if game_over_flag:
        return False
    
    print(f"Agent {agent.agent_id}: → Direct to {'key' if is_key else 'box'} at {pos}")
    move_to(agent, pos[0], pos[1])
    
    if game_over_flag:
        return False
    
    # Verify and claim
    data = get_data(agent)
    if data is None:
        return False
    
    val = data.get("cell_val", 0)
    if val == 1.0:
        info = get_item_owner(agent)
        if info and info.get("owner") == agent.agent_id:
            if is_key:
                agent.has_key = True
                print(f"Agent {agent.agent_id}: ★ KEY claimed at {pos}")
            else:
                agent.has_box = True
                agent.completed = True
                print(f"Agent {agent.agent_id}: ★ BOX claimed at {pos}")
            return True
    return False


def smart_find_item(agent, visited):
    """
    Smart item detection using triangulation:
    - val 0.5/0.6 = item is adjacent (1 step away) → check 8 neighbors ONCE
    - val 0.25/0.3 = item is 2 steps away → triangulate with 2 probes
    - val 0.35 = wall warning zone → SKIP (not an item!)
    Returns (is_own_item, position)
    """
    # Don't search if already completed
    if agent.completed:
        return False, None
    
    val = get_data(agent).get("cell_val", 0)
    pos = (agent.x, agent.y)
    
    if val <= 0:
        return False, None
    
    # Skip wall warning zone (0.35)
    if check_wall_danger(val):
        return False, None
    
    # Already on item OR on wall (both are 1.0)
    if val == 1.0:
        result = process_item(agent, visited)
        # If process_item returns None owner, it's a wall - skip it
        if result == (False, None):
            return False, None  # It's a wall, not an item
        return result
    
    # ADJACENT (0.5 or 0.6): item is 1 step away - just scan 8 neighbors once
    if val >= 0.5:
        for d in GRADIENT_DIRS:
            move(agent, d)
            check_val = get_data(agent).get("cell_val", 0)
            if check_val == 1.0:
                result = process_item(agent, visited)
                if result != (False, None):
                    return result
                # It was a wall, go back and continue
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
    global game_over_flag
    
    if game_over_flag:
        return False
    
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
    """Sweep a specific zone of the map with wall avoidance"""
    going_right = (agent.agent_id % 2 == 0)
    y = y_start
    previous_pos = (agent.x, agent.y)
    
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
            
            stuck_count = 0
            while agent.x != x or agent.y != target_y:
                old_x, old_y = agent.x, agent.y
                move_step(agent, x, target_y)
                
                # Check if stuck
                if agent.x == old_x and agent.y == old_y:
                    stuck_count += 1
                    if stuck_count > 3:
                        break
                else:
                    stuck_count = 0
                    previous_pos = (old_x, old_y)
                
                data = get_data(agent)
                if data is None:
                    continue
                val = data.get("cell_val", 0)
                
                # Detect wall warning zone
                if check_wall_danger(val):
                    contour_around_wall(agent, x, target_y, previous_pos)
                    break
                
                if val > 0 and val < 1.0 and not near_visited(agent, visited):
                    smart_find_item(agent, visited)
                    if check_known_items(agent):
                        return True
            
            data = get_data(agent)
            if data is None:
                continue
            val = data.get("cell_val", 0)
            
            if check_wall_danger(val):
                contour_around_wall(agent, x, target_y, previous_pos)
                continue
            
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
    success = sweep_zone(agent, visited, x1, x2, y1, y2, STEP)
    if success:
        return
    
    if agent.has_key and agent.has_box:
        return
    
    # Smart fallback: explore zones of OTHER agents
    for other_id in range(nb_agents):
        if other_id == agent.agent_id:
            continue
        
        if check_known_items(agent):
            return
        
        # Get other agent's zone
        ox1, ox2, oy1, oy2 = get_zone_for_agent(other_id, nb_agents, W, H)
        
        if not (agent.has_key and agent.has_box):
            print(f"Agent {agent.agent_id}: Exploring Agent {other_id}'s zone ({ox1},{oy1}) to ({ox2},{oy2})")
            success = sweep_zone(agent, visited, ox1, ox2, oy1, oy2, STEP)
            if success:
                return
    
    # Final fallback: full map sweep
    if not (agent.has_key and agent.has_box):
        print(f"Agent {agent.agent_id}: Full map sweep...")
        sweep_zone(agent, visited, 0, W, 0, H, STEP)


def agent_loop(agent):
    global game_over_flag
    print(f"Agent {agent.agent_id}: Start ({agent.x}, {agent.y})")
    visited = set()
    
    try:
        while not agent.completed and not game_over_flag:
            optimal_sweep(agent, visited)
            
            if game_over_flag:
                agent.completed = True
                break
            
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
    
    # Wait for all agents to complete or game over
    try:
        while not all(a.completed for a in agents) and not game_over_flag:
            time.sleep(1)
            
            if game_over_flag:
                print("💀 GAME OVER - An agent hit a wall!")
                break
            
            status = " | ".join(
                "✓" if a.completed else ("🔑" if a.has_key else "...")
                for a in agents
            )
            print(f"[{status}]")
    except KeyboardInterrupt:
        print("Stopped")
    
    if game_over_flag:
        print("💀 === GAME OVER === 💀")
    else:
        print("=== ALL DONE ===")

