import os
import sys
from google.adk.tools import FunctionTool, agent_tool
from google.adk.tools.agent_tool import AgentTool


# Add this path manipulation
current_dir = os.path.dirname(os.path.abspath(__file__))
project_root = os.path.join(current_dir, '..' , '..')
sys.path.insert(0, os.path.abspath(project_root))


from src_pulse.ai_agent import retrieve_relevant_chunks

def _retrieve_context(query: str) -> str:
    """
    Retrieve relevant policy document chunks from Pinecone to ground the agent's reasoning.
    
    This tool fetches relevant policy document chunks from Pinecone based on the user's 
    query text to provide context for generating accurate responses.
    
    Args:
        query (str): The user's query text to search for relevant context
        
    Returns:
        str: Combined text from relevant document chunks
    """

    chunks = retrieve_relevant_chunks(
        text=query,
        index_name="policypulse",
        api_key= os.environ.get("PINECONE_API_KEY"),
        top_k=5,
    )
        
    result = "\n\n".join(hit["text"] for hit in chunks)
    print(f"📝 Combined result length: {len(result)} characters")
    
    return result

RetrieveContextTool = FunctionTool(func=_retrieve_context)