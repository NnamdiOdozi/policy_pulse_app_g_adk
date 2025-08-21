# ============================================================================
# Corrected ADK-Compatible Search Tools Following Official Documentation
# ============================================================================

import os
import sys
import requests
import json
import time
from typing import Optional, Dict, Any

# Add path manipulation
current_dir = os.path.dirname(os.path.abspath(__file__))
project_root = os.path.join(current_dir, '..' , '..')
sys.path.insert(0, os.path.abspath(project_root))

from old_pulse.ai_agent import retrieve_relevant_chunks

# ========== CORRECT ADK FUNCTION TOOLS ==========
# Following ADK documentation: functions should be standalone, serializable

def search_with_tavily(query: str, max_results: int = 5) -> Dict[str, Any]:
    """
    Search the web using Tavily AI-powered search engine.
    
    Use this tool to find current information, recent developments, news, or 
    real-time data from the web. Tavily provides AI-generated direct answers 
    and is optimized for agent consumption.
    
    Best for: General web search, current events, news, fact verification
    
    Args:
        query (str): The search query. Be specific and detailed for best results.
        max_results (int): Maximum number of results to return (default: 5, max: 20)
        
    Returns:
        Dict[str, Any]: Search results with titles, URLs, content snippets, and 
                       optional direct answer from AI
    """
    try:
        api_key = os.getenv("TAVILY_API_KEY")
        if not api_key:
            return {"error": "TAVILY_API_KEY not found in environment variables"}
        
        endpoint = "https://api.tavily.com/search"
        payload = {
            "api_key": api_key,
            "query": query,
            "search_depth": "basic",
            "include_answer": True,
            "include_raw_content": False,
            "max_results": min(max_results, 20),
            "topic": "general"
        }
        
        response = requests.post(endpoint, json=payload, timeout=30)
        response.raise_for_status()
        data = response.json()
        
        if "error" in data:
            return {"error": f"Tavily API error: {data['error']}"}
        
        # Format results for agent consumption
        results = []
        for i, item in enumerate(data.get("results", []), 1):
            results.append({
                "position": i,
                "title": item.get("title", "No title"),
                "url": item.get("url", ""),
                "content": item.get("content", "No content available")
            })
        
        response_data = {
            "provider": "Tavily",
            "query": query,
            "results": results,
            "total_results": len(results)
        }
        
        # Add direct answer if available
        if data.get("answer"):
            response_data["direct_answer"] = data["answer"]
            
        return response_data
        
    except Exception as e:
        return {"error": f"Tavily search failed: {str(e)}"}


def search_with_exa(query: str, max_results: int = 5) -> Dict[str, Any]:
    """
    Search the web using Exa AI's neural/semantic search engine.
    
    Use this tool for semantic searches, finding similar content, discovering 
    high-quality articles, and conceptual research. Exa uses neural embeddings 
    to understand search intent better than keyword-based search.
    
    Best for: Conceptual searches, finding similar content, high-quality articles
    
    Args:
        query (str): The search query. Use natural language for best results.
        max_results (int): Maximum number of results to return (default: 5, max: 10)
        
    Returns:
        Dict[str, Any]: Search results with titles, URLs, content, and metadata
    """
    try:
        api_key = os.getenv("EXA_API_KEY")
        if not api_key:
            return {"error": "EXA_API_KEY not found in environment variables"}
        
        try:
            from exa_py import Exa
        except ImportError:
            return {"error": "exa_py package not installed. Run: pip install exa_py"}
        
        exa = Exa(api_key=api_key)
        
        # Use search_and_contents for better results
        exa_results = exa.search_and_contents(
            query=query,
            num_results=min(max_results, 10),
            type="auto",
            text={"max_characters": 1000}
        )
        
        results = []
        for i, item in enumerate(exa_results.results, 1):
            content = ""
            if hasattr(item, 'text') and item.text:
                content = item.text[:500] + "..." if len(item.text) > 500 else item.text
            
            results.append({
                "position": i,
                "title": item.title or "No title",
                "url": item.url or "",
                "content": content,
                "score": getattr(item, 'score', None),
                "published_date": getattr(item, 'published_date', None),
                "author": getattr(item, 'author', None)
            })
        
        return {
            "provider": "Exa",
            "query": query,
            "results": results,
            "total_results": len(results)
        }
        
    except Exception as e:
        return {"error": f"Exa search failed: {str(e)}"}


def search_with_serpapi(query: str, max_results: int = 5) -> Dict[str, Any]:
    """
    Search Google using SerpAPI for comprehensive, structured results.
    
    Use this tool for Google-like search results, structured data extraction,
    and when you need comprehensive web coverage with familiar ranking.
    
    Best for: Google search results, structured data, comprehensive coverage
    
    Args:
        query (str): The search query, similar to what you'd type in Google
        max_results (int): Maximum number of results to return (default: 5, max: 10)
        
    Returns:
        Dict[str, Any]: Google search results with titles, URLs, snippets
    """
    try:
        api_key = os.getenv("SERPAPI_API_KEY")
        if not api_key:
            return {"error": "SERPAPI_API_KEY not found in environment variables"}
        
        endpoint = "https://serpapi.com/search.json"
        params = {
            "engine": "google",
            "q": query,
            "num": min(max_results, 10),
            "api_key": api_key,
            "hl": "en",
            "gl": "uk"
        }
        
        response = requests.get(endpoint, params=params, timeout=30)
        response.raise_for_status()
        data = response.json()
        
        if "error" in data:
            return {"error": f"SerpAPI error: {data['error']}"}
        
        results = []
        for i, item in enumerate(data.get("organic_results", []), 1):
            results.append({
                "position": i,
                "title": item.get("title", "No title"),
                "url": item.get("link", ""),
                "content": item.get("snippet", "No content available")
            })
        
        return {
            "provider": "SerpAPI",
            "query": query,
            "results": results,
            "total_results": data.get("search_information", {}).get("total_results")
        }
        
    except Exception as e:
        return {"error": f"SerpAPI search failed: {str(e)}"}


def _retrieve_context(query: str) -> Dict[str, Any]:
    """
    Retrieve relevant policy document chunks from Pinecone based on a query.
    
    This tool fetches relevant policy document chunks from Pinecone vector database 
    based on the user's query text to provide contextual grounding for generating 
    accurate, policy-aware responses. The tool searches through pre-embedded policy 
    documents and returns the most semantically relevant chunks to inform the agent's 
    reasoning and ensure responses are grounded in actual policy content.
    
    Parameters:
    -----------
    query : str
        The user's query text used to search for relevant policy document context.
        This can be a question, topic, or any text that should be matched against
        the policy document corpus.
    
    Returns:
    --------
    Dict[str, Any]
        Combined text from the top-k most relevant document chunks, formatted
        for agent consumption. Contains the policy text that is semantically 
        related to the input query.
        
    Notes:
    ------
    - Uses the "policypulse" Pinecone index containing pre-embedded policy documents
    - Retrieves top 5 most relevant chunks by default (configurable in implementation)
    - Requires PINECONE_API_KEY environment variable to be set
    - Returns error dict if no relevant chunks found or if there are connection issues
    """
    try:
        chunks = retrieve_relevant_chunks(
            text=query,
            index_name="policypulse",
            api_key=os.environ.get("PINECONE_API_KEY"),
            top_k=5,
        )
        
        if not chunks:
            return {
                "provider": "Internal Knowledge Base", 
                "query": query,
                "results": [],
                "message": "No relevant policy documents found"
            }
        
        # Format chunks for agent consumption
        results = []
        for i, chunk in enumerate(chunks, 1):
            results.append({
                "position": i,
                "document_id": chunk.get("id", "unknown"),
                "content": chunk.get("text", ""),
                "score": chunk.get("score", 0),
                "metadata": chunk.get("metadata", {})
            })
        
        combined_text = "\n\n".join(chunk["text"] for chunk in chunks)
        
        return {
            "provider": "Internal Knowledge Base",
            "query": query,
            "results": results,
            "combined_context": combined_text,
            "total_results": len(results)
        }
        
    except Exception as e:
        return {"error": f"Internal search failed: {str(e)}"}


# ========== ADK TOOL INTEGRATION ==========
# Note: In your agent.py, use these functions directly in the tools list:
#
# from google.adk.agents import Agent
# from .tools import search_with_tavily, search_with_exa, _retrieve_context
#
# agent = Agent(
#     name="Search Agent",
#     model="gemini-1.5-pro",
#     tools=[
#         search_with_tavily,      # ADK auto-wraps as FunctionTool
#         search_with_exa,         # ADK auto-wraps as FunctionTool  
#         _retrieve_context        # ADK auto-wraps as FunctionTool
#     ]
# )

# ========== EXPORTS FOR BACKWARD COMPATIBILITY ==========
__all__ = [
    'search_with_tavily',
    'search_with_exa', 
    'search_with_serpapi',
    '_retrieve_context'
]