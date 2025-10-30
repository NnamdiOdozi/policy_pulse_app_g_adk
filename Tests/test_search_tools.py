# test_search_tools.py

import os
import sys

# === PATH SETUP ===
# UNUSUAL: We manipulate sys.path to allow imports from parent directories
current_dir = os.path.dirname(os.path.abspath(__file__))
project_root = os.path.join(current_dir, '..') 
sys.path.insert(0, os.path.abspath(project_root))

from agents.policy_pulse_agent.tools import get_search_tool

def test_all_tools():
    query = "latest workplace fertility benefits UK 2025"
    
    for provider in ["tavily", "exa", "serpapi"]:
        try:
            tool = get_search_tool(provider)
            result = tool.func(query)
            print(f"\n{provider.upper()} Results:")
            print(result[:200] + "..." if len(result) > 200 else result)
        except Exception as e:
            print(f"{provider} failed: {e}")

if __name__ == "__main__":
    test_all_tools()