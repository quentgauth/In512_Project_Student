#!/usr/bin/env python3
"""
Startup script to launch server + agents together.
Usage: python3 startup.py [nb_agents] [map_index]
"""

import subprocess
import sys
import time
import signal
import os

# Default parameters
NB_AGENTS = 4
MAP_INDEX = 1

def main():
    # Parse command line arguments
    nb_agents = int(sys.argv[1]) if len(sys.argv) > 1 else NB_AGENTS
    map_index = int(sys.argv[2]) if len(sys.argv) > 2 else MAP_INDEX
    
    script_dir = os.path.dirname(os.path.abspath(__file__))
    
    print(f"🚀 Starting simulation with {nb_agents} agents on map {map_index}")
    print("=" * 50)
    
    # Start server
    server_cmd = [sys.executable, "server.py", "-nb", str(nb_agents), "-mi", str(map_index)]
    print(f"📡 Starting server: {' '.join(server_cmd)}")
    server_proc = subprocess.Popen(
        server_cmd,
        cwd=script_dir,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True
    )
    
    # Wait for server to be ready
    time.sleep(1.5)
    
    # Check if server is still running
    if server_proc.poll() is not None:
        print("❌ Server failed to start!")
        return 1
    
    print("✅ Server ready!")
    print("-" * 50)
    
    # Start agents
    agent_cmd = [sys.executable, "main.py"]
    print(f"🤖 Starting agents: {' '.join(agent_cmd)}")
    agent_proc = subprocess.Popen(
        agent_cmd,
        cwd=script_dir
    )
    
    # Handle Ctrl+C gracefully
    def signal_handler(sig, frame):
        print("\n⏹️ Stopping simulation...")
        agent_proc.terminate()
        server_proc.terminate()
        sys.exit(0)
    
    signal.signal(signal.SIGINT, signal_handler)
    
    # Wait for agents to complete
    try:
        agent_proc.wait()
        print("\n" + "=" * 50)
        print("✅ Simulation complete!")
        print("📺 Window stays open - close it manually or press Ctrl+C")
        # Wait for the server (keeps pygame window open until user closes it)
        server_proc.wait()
    except KeyboardInterrupt:
        signal_handler(None, None)
    
    return 0

if __name__ == "__main__":
    sys.exit(main())
