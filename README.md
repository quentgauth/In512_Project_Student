# IN512 Project - Multi-Agent Key-Box Collection

## 👥 Team

| Last Name | First Name |
|-----------|------------|
| LAUPIES | Raphaël |
| SEITZ | Lucas |
| CHARDON DU RANQUET | Quentin |
| ABDELMALLEK | Enzo |

---

## 📋 Project Description

Autonomous multi-agent system where each agent must:
1. **Find its key** (identified by its color)
2. **Find its corresponding box**
3. **Avoid L-shaped walls** scattered across the map

Agents communicate through a broadcast system to share discovered item positions.

---

## 🚀 Quick Start

### Prerequisites
```bash
pip3 install pygame
```

### Launch (recommended method)
```bash
cd scripts
python3 startup.py [nb_agents] [map_id]

# Examples:
python3 startup.py 4 2    # 4 agents, map 2
python3 startup.py 2 1    # 2 agents, map 1
```

### Manual Launch
```bash
# Terminal 1 - Server
python3 scripts/server.py -nb 4 -mi 2

# Terminal 2 - Agents
python3 scripts/main.py
```

---

## 🧠 Implementation Architecture

### 1. Search Strategy (Sweep)

```
┌─────────────────────────────────────┐
│  Agent 0        │  Agent 1          │
│  Zone (0,0)     │  Zone (mid,0)     │
│  → (mid,mid)    │  → (W,mid)        │
├─────────────────┼───────────────────┤
│  Agent 2        │  Agent 3          │
│  Zone (0,mid)   │  Zone (mid,mid)   │
│  → (mid,H)      │  → (W,H)          │
└─────────────────────────────────────┘
```

- **Quadrant division**: Each agent explores a dedicated zone
- **Zigzag movement**: Horizontal sweep with alternating direction
- **4-cell step size**: Optimal for detecting all items (detection halo = 2 cells)
- **Neighbor zone exploration**: If an agent finishes its zone, it explores others'

### 2. Item Detection

Items (keys/boxes) emit a detection "halo":
- `1.0`: On the item
- `0.5-0.6`: 1 cell away
- `0.25-0.3`: 2 cells away

**Triangulation algorithm**:
1. Halo detection (value > 0)
2. Probing in 8 directions
3. Following gradient to the item

### 3. Communication System

```python
# When an agent finds an item:
broadcast(agent, item_type, owner, position)

# Other agents receive:
- Exact item position
- Owner (which agent it belongs to)
- Type (KEY or BOX)
```

Each agent maintains:
- `my_key_pos` / `my_box_pos`: Positions of its own items
- `other_keys` / `other_boxes`: Other agents' items

### 4. Wall Avoidance

#### Detection
- Value `0.35` = Danger zone (1 cell from wall)
- Value `1.0` on wall cell = **GAME OVER**

#### Bypass Strategy

```
Initial position → Blocked direction
        ↓
    [RETREAT] Immediate fallback
        ↓
    [SCAN] Analyze 8 directions
        ↓
    [BYPASS] Perpendicular movement
        ↓
    [RESUME] Resume toward target
```

#### Path Memory
- `blocked_zones`: Memorized problematic positions
- `failed_bypasses`: Bypass directions that failed
- Prevents repeating the same mistakes

### 5. Loop Handling

**Detection**: If a position is visited 3+ times → loop detected

**Resolution**:
1. Systematic bypass (perpendicular to target direction)
2. Direction rotation with each attempt
3. Abandon after 5 attempts with strategy change

---

## 📁 File Structure

```
scripts/
├── startup.py      # 🚀 Launch script (server + agents)
├── main.py         # 🤖 Agent logic (our implementation)
├── server.py       # 🖥️ Game server
├── game.py         # 🎮 Game logic (walls, items, collision)
├── gui.py          # 📺 Pygame graphical interface
├── agent.py        # 📡 Agent network communication
├── network.py      # 🔌 Network layer
└── my_constants.py # 📋 Constants (directions, types, etc.)

resources/
├── config.json     # ⚙️ Map configuration (item/wall positions)
└── img/            # 🖼️ Graphical assets
```

---

## 🗺️ Map Configuration

Each map defines:
- Agent spawn positions
- Key and box positions
- L-shaped wall positions and rotations

**Available maps**: 1, 2, 3

```json
{
  "wall_1": { "x": 25, "y": 8, "rotation": 1 },
  "wall_2": { "x": 10, "y": 22, "rotation": 3 }
}
```

L-wall rotations:
- `0`: ███ + left column
- `1`: ███ + right column  
- `2`: Left column + ███
- `3`: Right column + ███

---

## 📊 Display

The Pygame window shows:
- **Header**: Step counter for each agent (colored)
- **Grid**: 35x30 cells
- **Colored traces**: Path traveled by each agent
- **Walls**: Gray zones (dark = wall, light = danger zone)
- **Items**: Keys 🔑 and boxes 📦 with colored borders

---

## ⚙️ Key Parameters

| Parameter | Value | Description |
|-----------|-------|-------------|
| `STEP` | 4 | Spacing between sweep lines |
| `MAX_BYPASS_STEPS` | 15 | Max steps to bypass a wall |
| `MIN_BYPASS_BEFORE_RETRY` | 3 | Minimum steps before retrying toward target |
| `WALL_WARNING_PERCENTAGE` | 0.35 | Value indicating wall proximity |

---

## 🎯 Implemented Optimizations

1. **Inter-agent communication**: Immediate discovery sharing
2. **Direct access**: Once an item is located, agent goes directly
3. **Path memory**: Avoids repeating the same mistakes
4. **Diagonal movements**: Priority to diagonals for shorter paths
5. **Adaptive exploration**: Agents explore other zones if needed

---

## 📝 License

Apache License 2.0