# ============================================================================
# Corrected ADK-Compatible Search Tools Following Official Documentation
# ============================================================================

import os
import sys
import requests
import json
import time
from typing import Optional, Dict, Any

from google.adk.agents import Agent
from google.adk.tools.agent_tool import AgentTool
from google.adk.tools import  google_search

# Add path manipulation
current_dir = os.path.dirname(os.path.abspath(__file__))
project_root = os.path.join(current_dir, '..' , '..')
sys.path.insert(0, os.path.abspath(project_root))

from old_pulse.ai_agent import retrieve_relevant_chunks


# ========== CORRECT ADK FUNCTION TOOLS ==========
# Following ADK documentation: functions should be standalone, serializable

def search_with_tavily_faq(query: str, max_results: int = 8, char_limit: int = 1000, search_depth: str = "basic", include_raw: bool = False) -> Dict[str, Any]:

    """
        Search the web using Tavily AI-powered search engine with prioritized domains.
        
        Use this tool to find current information, recent developments, news, or 
        real-time data from the web. Tavily provides AI-generated direct answers 
        and is optimized for agent consumption.
        
        Best for: FAQ responses, quick questions, fact verification
        
        Args:
            query (str): The search query which should be in double quotes. Be specific and detailed for best results.
            max_results (int): Maximum number of results to return (default: 8, max: 20)
            char_limit (int): Maximum characters per result content (default: 1000)
            search_depth (str): Search depth "basic" or "advanced" (default: "basic")
            include_raw (bool): Whether to include raw content (default: False)
            
        Returns:
            Dict[str, Any]: Search results with titles, URLs, and content snippets


        To ensure that a response is returned do not use the word "fertility" in the query string. Instead use phrases like "reproductive health", OR "reproductive health support", OR "assisted reproductive services", OR "conception assistance", depending on the context
        """

# Define your preferred domains (fixed syntax errors in the list)
    preferred_domains = [
            "*.gov.uk",       # UK government websites
            "*.ac.uk",        # UK academic institutions
            "*.nhs.uk",       # UK healthcare resources
            "peppy.health",
            "getjuniper.co.uk",
            "fertifa.com",  # Added missing comma
            "fertilitynetworkuk.org",  # Added missing comma
            "hertilityhealth.com",  # Added missing comma
            "resolve.org",  # Simplified URL to domain
            "fertilitymattersatwork.com",  # Added missing comma
            "bournhall.co.uk",  # Added missing comma
            "unfpa.org",  # Added missing comma
            "gaiafamily.com"  # Simplified URL to domain
    ]

    # Call the FAQ function with report-optimized parameters
    result = _search_with_tavily(
        query=query,
        max_results=max_results,
        char_limit=10000,  # 5,000 chars instead of 500
        search_depth="advanced",
        include_raw=True,  # Include raw content for more detail
        preferred_domains=preferred_domains
    )   

    return result

def _search_with_tavily(query: str, max_results: int = 8, char_limit: int = 1000, search_depth: str = "basic", include_raw: bool = False, preferred_domains:list[str]=None) -> Dict[str, Any]:
    """
    Search the web using Tavily AI-powered search engine with prioritized domains.
    
    Use this tool to find current information, recent developments, news, or 
    real-time data from the web. Tavily provides AI-generated direct answers 
    and is optimized for agent consumption.
    
    Best for: FAQ responses, quick questions, fact verification
    
    Args:
        query (str): The search query which should be in double quotes. Be specific and detailed for best results.
        max_results (int): Maximum number of results to return (default: 8, max: 20)
        char_limit (int): Maximum characters per result content (default: 1000)
        search_depth (str): Search depth "basic" or "advanced" (default: "basic")
        include_raw (bool): Whether to include raw content (default: False)
        
    Returns:
        Dict[str, Any]: Search results with titles, URLs, and content snippets


    To ensure that a response is returned do not use the word "fertility" in the query string. Instead use phrases like "reproductive health", OR "reproductive health support", OR "assisted reproductive services", OR "conception assistance", depending on the context
    """
   
    try:
        api_key = os.getenv("TAVILY_API_KEY")
        if not api_key:
            return {"error": "TAVILY_API_KEY not found in environment variables"}
        
        # Step 1: Search preferred domains first
        preferred_results = _tavily_search(
            api_key, 
            query, 
            search_depth, 
            include_raw, 
            max_results * 2,  # Request more results to ensure we get enough
            preferred_domains
        )
        
        # Step 2: If not enough results from preferred domains, do a general search
        preferred_count = len(preferred_results.get("results", []))
        
        if preferred_count < max_results:
            # Do a general search without domain restrictions
            general_results = _tavily_search(
                api_key,
                query,
                search_depth,
                include_raw,
                max_results,
                None  # No domain restrictions
            )
            
            # Extract URLs from preferred results to avoid duplicates
            preferred_urls = [item.get("url", "") for item in preferred_results.get("results", [])]
            
            # Add unique results from general search
            for item in general_results.get("results", []):
                if item.get("url", "") not in preferred_urls:
                    preferred_results["results"].append(item)
        
        # Format and process the combined results
        formatted_results = []
        for i, item in enumerate(preferred_results.get("results", []), 1):
            # Handle both raw and regular content
            content = item.get("content", "No content available")
            raw_content = item.get("raw_content", "")
            
            # Use raw_content if available and requested
            full_content = raw_content if include_raw and raw_content else content
            
            # Truncate to specified char limit
            if len(full_content) > char_limit:
                full_content = full_content[:char_limit] + "..."
            
            formatted_results.append({
                "position": i,
                "title": item.get("title", "No title"),
                "url": item.get("url", ""),
                "content": full_content,
                "score": item.get("score", None),
                "published_date": item.get("published_date", None),
                "source_type": "preferred" if any(domain in item.get("url", "") for domain in preferred_domains) else "general"
            })
        
        # Limit to requested max_results
        formatted_results = formatted_results[:max_results]
        
        # Build final response
        response_data = {
            "provider": "Tavily FAQ",
            "query": query,
            "results": formatted_results,
            "total_results": len(formatted_results)
        }
        
        # Add direct answer if available
        if preferred_results.get("answer"):
            response_data["direct_answer"] = preferred_results["answer"]
            
        return response_data
        
    except Exception as e:
        return {"error": f"Tavily FAQ search failed: {str(e)}"}

def _tavily_search(api_key: str, query: str, search_depth: str, include_raw: bool, 
                  max_results: int, domains: list[str] = None) -> Dict[str, Any]:
    """Helper function to perform a Tavily search with the given parameters."""
    endpoint = "https://api.tavily.com/search"
    payload = {
        "api_key": api_key,
        "query": query,
        "search_depth": search_depth,
        "include_answer": True,
        "include_raw_content": include_raw,
        "max_results": min(max_results, 20),
        "topic": "general"
    }
    
    # Only add include_domains if domains are specified
    if domains:
        payload["include_domains"] = domains
    
    response = requests.post(endpoint, json=payload, timeout=30)
    response.raise_for_status()
    return response.json()


def search_with_tavily_report(query: str, max_results: int = 8) -> Dict[str, Any]:
    """
    Search the web using Tavily AI for report writing with comprehensive content.
    
    Use this tool for detailed research, report writing, and comprehensive analysis.
    This is a wrapper function that calls search_with_tavily_faq with parameters
    optimized for longer, more detailed content.
    
    Best for: Report writing, detailed research, comprehensive analysis
    
    Args:
        query (str): The search query. Be specific and detailed for best results.
        max_results (int): Maximum number of results to return (default: 8, max: 20)
        
    Returns:
        Dict[str, Any]: Search results with titles, URLs, and comprehensive content

     To ensure that a response is returned do not use the word "fertility" in the query string. Instead use words like "reproductive health", "reproductive health support", "assisted reproductive services", "conception assistance"
    
    """

    # Define your preferred domains (fixed syntax errors in the list)
    preferred_domains = []
    
    # Call the FAQ function with report-optimized parameters
    result = _search_with_tavily(
        query=query,
        max_results=max_results,
        char_limit=10000,  # 10,000 chars instead of 500
        search_depth="advanced",
        include_raw=True,  # Include raw content for more detail
        preferred_domains=preferred_domains
    )
    
    # Update provider name to indicate this is the report version
    if "provider" in result:
        result["provider"] = "Tavily Report"
    
    return result


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
        
        # Use search_and_contents - REVERTED to original settings
        exa_results = exa.search_and_contents(
            query=query,
            num_results=min(max_results, 10),
            type="auto",
            text={"max_characters": 1000}  # REVERTED back to 1000
        )
        
        results = []
        for i, item in enumerate(exa_results.results, 1):
            # REVERTED: Truncate content to 500 chars for context management
            content = ""
            if hasattr(item, 'text') and item.text:
                content = item.text[:500] + "..." if len(item.text) > 500 else item.text
            elif hasattr(item, 'content') and item.content:
                content = item.content[:500] + "..." if len(item.content) > 500 else item.content
            
            results.append({
                "position": i,
                "title": item.title or "No title",
                "url": item.url or "",
                "content": content,  # REVERTED: 500 char limit
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
    
    Best for: Traditional Google search, academic papers, official sources
    
    Args:
        query (str): The search query
        max_results (int): Maximum number of results to return (default: 5, max: 100)
        
    Returns:
        Dict[str, Any]: Search results with titles, URLs, snippets, and metadata
    """
    try:
        api_key = os.getenv("SERPAPI_KEY")
        if not api_key:
            return {"error": "SERPAPI_KEY not found in environment variables"}
        
        params = {
            "api_key": api_key,
            "engine": "google",
            "q": query,
            "num": min(max_results, 100),
            "location": "United Kingdom",  # Default location based on Policy Pulse context
            "hl": "en",
            "gl": "gb"
        }
        
        response = requests.get("https://serpapi.com/search", params=params, timeout=30)
        response.raise_for_status()
        data = response.json()
        
        if "error" in data:
            return {"error": f"SerpAPI error: {data['error']}"}
        
        # Extract organic results
        organic_results = data.get("organic_results", [])
        
        results = []
        for i, item in enumerate(organic_results, 1):
            results.append({
                "position": item.get("position", i),
                "title": item.get("title", "No title"),
                "url": item.get("link", ""),
                "content": item.get("snippet", "No snippet available"),
                "displayed_link": item.get("displayed_link", ""),
                "date": item.get("date", None)
            })
        
        # Include knowledge panel if available
        knowledge_graph = data.get("knowledge_graph", {})
        answer_box = data.get("answer_box", {})
        
        response_data = {
            "provider": "SerpAPI",
            "query": query,
            "results": results,
            "total_results": len(results)
        }
        
        if knowledge_graph:
            response_data["knowledge_graph"] = knowledge_graph
        if answer_box:
            response_data["answer_box"] = answer_box
            
        return response_data
        
    except Exception as e:
        return {"error": f"SerpAPI search failed: {str(e)}"}


def _retrieve_context(query: str, max_chunks: int = 5) -> Dict[str, Any]:
    """
    Retrieve relevant context from the Policy Pulse knowledge base using RAG.

    Note that the RAG daatbase may not have the most up to dat information
    
    This function searches the internal vector database for relevant policy 
    documents, regulatory guidance, and training content to provide context 
    for AI responses.
    
    Args:
        query (str): The search query for retrieving relevant context
        max_chunks (int): Maximum number of document chunks to retrieve (default: 5)
        
    Returns:
        Dict[str, Any]: Retrieved context chunks with metadata and citations
    """
    try:
        # Use the existing retrieve_relevant_chunks function
        chunks = retrieve_relevant_chunks(
            text=query,
            index_name="policypulse",
            api_key=os.environ.get("PINECONE_API_KEY"),
            top_k=max_chunks,
        )
        
        if not chunks:
            return {
                "provider": "PolicyPulse RAG",
                "query": query,
                "chunks": [],
                "total_chunks": 0,
                "message": "No relevant context found in knowledge base"
            }
        
        # Format chunks for consistency with search tools
        formatted_chunks = []
        for i, chunk in enumerate(chunks, 1):
            # Handle different chunk formats
            if isinstance(chunk, dict):
                formatted_chunks.append({
                    "position": i,
                    "content": chunk.get("text", chunk.get("content", "")),
                    "source": chunk.get("source", "Unknown"),
                    "score": chunk.get("score", None),
                    "metadata": chunk.get("metadata", {})
                })
            elif isinstance(chunk, str):
                formatted_chunks.append({
                    "position": i,
                    "content": chunk,
                    "source": "PolicyPulse Knowledge Base",
                    "score": None,
                    "metadata": {}
                })
            else:
                # Handle other formats
                formatted_chunks.append({
                    "position": i,
                    "content": str(chunk),
                    "source": "PolicyPulse Knowledge Base",
                    "score": None,
                    "metadata": {}
                })
        
        return {
            "provider": "PolicyPulse RAG",
            "query": query,
            "chunks": formatted_chunks,
            "total_chunks": len(formatted_chunks)
        }
        
    except Exception as e:
        return {"error": f"Context retrieval failed: {str(e)}"}


# ========== UTILITY FUNCTIONS ==========

def get_search_tool(provider: str = "tavily"):
    """
    Get a search tool by provider name.
    
    Args:
        provider (str): Provider name ("tavily", "exa", "serpapi")
        
    Returns:
        Callable: The search function for the specified provider
    """
    providers = {
        "tavily": search_with_tavily_faq,
        "exa": search_with_exa,
        "serpapi": search_with_serpapi
    }
    
    if provider not in providers:
        raise ValueError(f"Unknown provider: {provider}. Available: {list(providers.keys())}")
    
    return providers[provider]


def search_all_providers(query: str, max_results: int = 3) -> Dict[str, Any]:
    """
    Search using all available providers and combine results.
    
    Args:
        query (str): The search query
        max_results (int): Maximum results per provider
        
    Returns:
        Dict[str, Any]: Combined results from all providers
    """
    combined_results = {
        "query": query,
        "providers": {},
        "total_results": 0
    }
    
    providers = ["tavily", "exa", "serpapi"]
    
    for provider in providers:
        try:
            search_func = get_search_tool(provider)
            result = search_func(query, max_results)
            
            if "error" not in result:
                combined_results["providers"][provider] = result
                combined_results["total_results"] += result.get("total_results", 0)
        except Exception as e:
            combined_results["providers"][provider] = {"error": str(e)}
    
    return combined_results


# ========== LEGACY AGENT TOOL WRAPPERS ==========
# These are kept for backward compatibility with the existing agent system



# Google search agent (existing)
search_agent = Agent(
    name="google_search_agent",
    model="gemini-1.5-pro",
    instruction="You are a search agent. Use the search tool to help answer user queries.",
    tools=[google_search]
)
search_with_google = AgentTool(search_agent)


# ========== ADK TOOL INTEGRATION ==========
# Note: In your agent.py, use these functions directly in the tools list:
#
# from google.adk.agents import Agent
# from .tools import search_with_tavily_faq, search_with_tavily_report, search_with_exa, _retrieve_context
#
# agent = Agent(
#     name="Search Agent",
#     model="gemini-1.5-pro",
#     tools=[
#         search_with_tavily_faq,      # ADK auto-wraps as FunctionTool
#         search_with_tavily_report,   # ADK auto-wraps as FunctionTool
#         search_with_exa,             # ADK auto-wraps as FunctionTool  
#         _retrieve_context            # ADK auto-wraps as FunctionTool
#     ]
# )

# ========== EXPORTS FOR BACKWARD COMPATIBILITY ==========
__all__ = [
    'search_with_tavily_faq',
    'search_with_tavily_report',
    'search_with_exa', 
    'search_with_serpapi',
    'search_with_google',
    '_retrieve_context',
    'get_search_tool',
    'search_all_providers'
]