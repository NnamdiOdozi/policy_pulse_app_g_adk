# test_search_only.py
import os
import requests
import json
from pprint import pprint

# Load environment variables
from dotenv import load_dotenv
load_dotenv()

def test_tavily_direct():
    """Test Tavily search without any ADK dependencies."""
    api_key = os.getenv("TAVILY_API_KEY")
    if not api_key:
        print("❌ TAVILY_API_KEY not found")
        return
   
    endpoint = "https://api.tavily.com/search"
    payload = {
        "api_key": api_key,
        "query": "workplace maternity leave policies",
        "search_depth": "advanced",
        "include_answer": True,
        "max_results": 5
    }
   
    try:
        response = requests.post(endpoint, json=payload, timeout=30)
        response.raise_for_status()
        data = response.json()
        print("✅ Tavily search successful")
        print(f"   Results: {len(data.get('results', []))}")
        
        # Pretty print the results with spacing
        print("\n   Results details:")
        for i, result in enumerate(data.get('results', [])):
            print(f"\n   [Result {i+1}]")
            print(f"   Title: {result.get('title', 'No title')}")
            print(f"   URL: {result.get('url', 'No URL')}")
            print(f"   Content: {result.get('content', 'No content')[:400]}...")
        
        # Print the full answer without arbitrary truncation
        answer = data.get('answer', 'None')
        print("\n   Answer:")
        print(f"   {answer}")
        
        # Also print the answer length for reference
        print(f"\n   Answer length: {len(answer)} characters")
        
    except Exception as e:
        print(f"❌ Tavily search failed: {e}")

def test_exa_direct():
    """Test Exa search without any ADK dependencies."""
    try:
        from exa_py import Exa
    except ImportError:
        print("❌ exa_py not installed")
        return
   
    api_key = os.getenv("EXA_API_KEY")
    if not api_key:
        print("❌ EXA_API_KEY not found")
        return
   
    try:
        exa = Exa(api_key=api_key)
        # Explicitly request text content
        results = exa.search_and_contents("workplace policies", num_results=5)
        print("✅ Exa search successful")
        print(f"   Results: {len(results.results)}")
        
        # Print result details with the correct attributes
        print("\n   Results details:")
        for i, result in enumerate(results.results):
            print(f"\n   [Result {i+1}]")
            print(f"   Title: {result.title}")
            print(f"   URL: {result.url}")
            
            # Check if text content is available
            if hasattr(result, 'text') and result.text:
                print(f"   Content: {result.text[:400]}...")
            else:
                print("   No content available")
                
            # Print all available attributes for debugging
            print("\n   Available attributes:")
            for attr in dir(result):
                if not attr.startswith('_') and not callable(getattr(result, attr)):
                    print(f"   - {attr}")
       
    except Exception as e:
        print(f"❌ Exa search failed: {e}")

if __name__ == "__main__":
    print("Testing search APIs directly...")
    test_tavily_direct()
    test_exa_direct()
    print("Done!")