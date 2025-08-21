# test_search_tools.py
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