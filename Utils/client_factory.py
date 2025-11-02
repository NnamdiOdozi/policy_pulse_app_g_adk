# In client_factory.py
"""
Client factory for creating API clients.
Centralizes client creation logic.
"""
import os
import voyageai
from pymilvus import MilvusClient
from langchain_openai import ChatOpenAI
from dotenv import load_dotenv

load_dotenv()

def create_voyage_client():
    """Create and return a Voyage AI client."""
    api_key = os.getenv("VOYAGE_API_KEY")
    if not api_key:
        raise ValueError("VOYAGE_API_KEY not found in environment")
    return voyageai.Client(api_key=api_key)

def create_milvus_client():
    return MilvusClient(
        uri=os.getenv("ZILLIZ_CLOUD_URI"),
        token=os.getenv("ZILLIZ_API_KEY")
    )

def create_openai_client(model: str = "gpt-4o-mini"):
    """Create and return an OpenAI LangChain client."""
    api_key = os.getenv("OPENAI_API_KEY")
    if not api_key:
        raise ValueError("OPENAI_API_KEY not found in environment")
    
    return ChatOpenAI(
        model=model,
        temperature=0.0,
        api_key=api_key,
        request_timeout=120,
        max_retries=5
    )
# ADD THIS NEW FUNCTION:
def create_reranker_client():
    """
    Create and return a FlagEmbedding reranker client.
    Only creates if RERANKER_ENABLED=true in environment.
    
    Returns:
        FlagReranker instance or None if disabled
    """
    reranker_enabled = os.getenv("RERANKER_ENABLED", "false").lower() == "true"
    
    if not reranker_enabled:
        return None
    
    try:
        from FlagEmbedding import FlagReranker
        
        # Detect if GPU is available
        use_gpu = False #torch.cuda.is_available()
        
        reranker = FlagReranker(
            'BAAI/bge-reranker-v2-m3',
            use_fp16=use_gpu,  # Only use fp16 on GPU
            device='cuda' if use_gpu else 'cpu'
        )
        
        print(f"Reranker initialized on {'GPU' if use_gpu else 'CPU'}")
        return reranker
    except ImportError:
        print("Warning: FlagEmbedding not installed. Reranking disabled.")
        return None