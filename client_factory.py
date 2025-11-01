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