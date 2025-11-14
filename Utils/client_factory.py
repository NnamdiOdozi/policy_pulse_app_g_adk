# In client_factory.py
"""
Client factory for creating API and db clients.
Centralizes client creation logic.
"""
import os
import voyageai
from pymilvus import MilvusClient
from langchain_openai import ChatOpenAI

from sqlalchemy import create_engine
from sqlalchemy.pool import QueuePool
from psycopg2.extras import RealDictCursor
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

def create_openai_client(model: str = "gpt-5-nano"):
    """Create and return an OpenAI LangChain client."""
    api_key = os.getenv("OPENAI_API_KEY")
    if not api_key:
        raise ValueError("OPENAI_API_KEY not found in environment")
    
    return ChatOpenAI(
        model=model,
        use_responses_api=True,
        reasoning={"effort": "minimal"},
        temperature=0.0,
        api_key=api_key,
        request_timeout=120,
        max_retries=5,
        verbosity="low",
        max_completion_tokens=30
    )

def create_reranker_client():
    """
    Create and return a reranker client.
    Returns the reranker API client object directly (not a wrapper).
    
    Returns:
        Reranker Client instance or None if disabled
    """
    reranker_enabled = os.getenv("RERANKER_ENABLED", "false").lower() == "true"
    
    if not reranker_enabled:
        return None
    
    try:
        api_key = os.getenv("VOYAGE_API_KEY")
        if not api_key:
            print("Warning: VOYAGE_API_KEY not found. Reranking disabled.")
            return None
        
        import voyageai
        reranker_model = os.getenv("RERANKER_MODEL", "rerank-2.5-lite") # I should also try the full 2.5 model since this might give better results
        print(f"Reranker enabled with Voyage model: {reranker_model}")
        
        return voyageai.Client(api_key=api_key)
        
    except ImportError:
        print("Warning: voyageai package not installed. Reranking disabled.")
        return None
    except Exception as e:
        print(f"Warning: Failed to initialize Voyage reranker: {e}")
        return None
    
# Global connection pool (singleton pattern)
_db_engine = None


class PooledConnection:
    """
    Wrapper to make SQLAlchemy connections compatible with ADK and psycopg2 expectations.
    
    Provides context manager support and proper cursor factory.
    """
    def __init__(self, raw_conn):
        self.raw_conn = raw_conn
    
    def __enter__(self):
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        self.raw_conn.close()
    
    def cursor(self):
        """Return RealDictCursor for dictionary-style row access."""
        return self.raw_conn.cursor(cursor_factory=RealDictCursor)
    
    def commit(self):
        return self.raw_conn.commit()
    
    def rollback(self):
        return self.raw_conn.rollback()


def create_db_connection():
    """
    Create a pooled database connection.

    WHY POOLING? Opening/closing DB connections is expensive.
    Connection pooling maintains a pool of reusable connections.
    
    TRADE-OFFS:
    - More memory usage (keeping connections open)
    - Better performance (no connection overhead)
    - Requires proper cleanup (use context managers)
    
    Uses SQLAlchemy connection pooling for performance:
    - pool_size=5: Keep 5 connections always open
    - max_overflow=10: Allow up to 15 total under load
    - pool_recycle=240: Recycle connections every 4 minutes
    - pool_pre_ping=True: Test connections before use
    
    Returns:
        PooledConnection: Context manager-compatible connection
    """
    global _db_engine
    
    if _db_engine is None:
        db_url = os.getenv("DATABASE_URL")
        if not db_url:
            raise ValueError("DATABASE_URL not found in environment")
        
        _db_engine = create_engine(
            db_url,
            poolclass=QueuePool,
            pool_size=5,
            max_overflow=10,
            pool_recycle=240,
            pool_pre_ping=True,
            connect_args={
                "sslmode": "require",
                "keepalives_idle": 60,
                "keepalives_interval": 15,
                "keepalives_count": 5,
            }
        )
        print("Database connection pool initialized")
    
    raw_conn = _db_engine.raw_connection()
    return PooledConnection(raw_conn)


# Alias for backward compatibility
get_db_connection = create_db_connection