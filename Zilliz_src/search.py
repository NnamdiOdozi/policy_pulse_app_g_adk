import os
import sys
import datetime
from pathlib import Path
from typing import List, Dict, Any, Optional
import argparse

# For embeddings and vector database
from pymilvus import  AnnSearchRequest, RRFRanker, Function, FunctionType

# === PATH SETUP ===
# UNUSUAL: We manipulate sys.path to allow imports from parent directories
from pathlib import Path

# Calculate project root based on file location
current_file = Path(__file__).resolve()
project_root = current_file.parent.parent  # Adjust levels as needed
sys.path.insert(0, str(project_root))

import Utils.client_factory as client_factory

# Load environment variables
from dotenv import load_dotenv
load_dotenv()


"""
DUAL TEXT FIELD ARCHITECTURE

This module uses two text fields with distinct purposes:

1. TEXT FIELD (Display-Only)
   - Purpose: User-facing content
   - Content: Clean chunk text without metadata clutter
   - Used for: UI display, citations, debugging
   - Maintained: Updated when metadata changes
   - NOT used for: Search operations, embeddings

2. ENRICHED_TEXT FIELD (Search-Only)
   - Purpose: Search operations and LLM context
   - Content: Chunk text + metadata (summary, context, keywords, etc.)
   - Used for:
     * Vector embedding generation (semantic search)
     * TEXT_MATCH keyword search (hybrid search)
     * LLM context when generating answers
   - Maintained: Created at indexing time, NOT updated with metadata changes
   - NOT used for: Direct user display

SEARCH CONSISTENCY:
Both semantic search (vector) and keyword search (TEXT_MATCH) operate on the
same enriched_text content. This ensures that:
- Vector embeddings capture full context including metadata
- Keyword matching benefits from same metadata enrichment
- Results are consistent across search methods

TRADE-OFFS:
- Storage: ~2x text storage (enriched text is 1.5-2x larger than raw)
- Staleness: Enriched text may contain outdated metadata if files are renamed
  (this is intentional to avoid re-embedding)
- Benefit: Consistent search behavior, rich LLM context, clean user display
"""

# Configuration
OPENAI_API_KEY = os.environ.get("OPENAI_API_KEY")  # For generating summaries
VOYAGE_API_KEY = os.environ.get("VOYAGE_API_KEY")
ZILLIZ_CLOUD_URI = os.environ.get("ZILLIZ_CLOUD_URI")
ZILLIZ_CLOUD_TOKEN = os.environ.get("ZILLIZ_API_KEY")
BATCH_SIZE = 100  # Adjust based on your data and API limits
COLLECTION_NAME = os.getenv("ZILLIZ_COLLECTION_NAME")
EMBEDDING_DIM = 1024  # Voyage 3 Large dimension
EMBEDDING_MODEL_NAME = "voyage-3-large"


RERANKER_ENABLED = os.getenv("RERANKER_ENABLED", "false").lower() == "true"

# === PATH SETUP ===
# UNUSUAL: We manipulate sys.path to allow imports from parent directories
current_dir = os.path.dirname(os.path.abspath(__file__))
project_root = os.path.join(current_dir, '..') 
sys.path.insert(0, os.path.abspath(project_root))


class ZillizSearchTool:
    def __init__(self, voyage_client, milvus_client, reranker=None):
        """
        Initialize ZillizSearchTool with injected clients.
        
        Args:
            voyage_client: Voyage AI client for embeddings
            milvus_client: Milvus/Zilliz client for vector database
            reranker_client: Optional FlagReranker for result reranking
        """
        self.voyage_client = voyage_client
        self.zilliz_client = milvus_client
        self.reranker = reranker
        
        # Log reranker status
        if self.reranker:
            print("ZillizSearchTool initialized WITH reranking")
        else:
            print("ZillizSearchTool initialized WITHOUT reranking")
        
              
        # Create logs directory if it doesn't exist
        LOG_DIR_NAME = "search_logs"
        self.logs_dir = Path(__file__).resolve().parent / LOG_DIR_NAME
        os.makedirs(self.logs_dir, exist_ok=True)

       

        # Create single log file for this script run and need to write to file after search is completed - this is not currently being used and I should consider removing later on.
        timestamp = datetime.datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
        self.current_log_file = os.path.join(self.logs_dir, f"chunks_log_{timestamp}.json")
        self.log_data = {
            "script_run": {
            "timestamp": datetime.datetime.now().isoformat(),
            "voyage_model": EMBEDDING_MODEL_NAME,
            "embedding_dimension": EMBEDDING_DIM
            },
            "chunks": []
        }
        
        print("Clients initialized successfully")

    def search_chunks(self, collection_name: str, query: str, limit: int = 5, 
                metadata_filter: Optional[str] = None) -> List[Dict[str, Any]]:
        """
        Semantic search using vector embeddings generated from enriched text.
        
        Returns both text fields and other fields:
        - text: Clean chunk for user display
        - enriched_text: Full context for LLM reasoning
        
        The vector search operates on embeddings generated from enriched_text,
        ensuring semantic similarity includes metadata context.


        """
        if RERANKER_ENABLED and self.reranker:
            limit_r = 2 * limit  # Fetch more for reranking
        else:
            limit_r = limit        

        try:
            # Generate embedding for the query
            query_embedding = self.voyage_client.embed(
                [query], 
                model=EMBEDDING_MODEL_NAME, 
                input_type="query",
                output_dimension=EMBEDDING_DIM
            ).embeddings[0]
            
            # Define output fields - ensure they match your schema
            output_fields = [
                "text", "enriched_text", "chunk_summary", "section_title", "document_summary",
                "filename", "file_type", "section_context", "semantic_keywords"
            ]
            
            # Perform the search
            search_params = {
                "data": [query_embedding],
                "limit": limit_r,
                "output_fields": output_fields,
                "anns_field": "vector",  # add: explicit vector field
                "search_params": {"metric_type": "COSINE", "params": {"ef": 256}},  # add: HNSW recall
            }
            
            # Add metadata filter if provided and properly format it
            if metadata_filter:
                # Make sure the filter syntax is correct for Zilliz
                # Example: file_type == "pdf" should work if file_type field exists
                search_params["filter"] = metadata_filter
                print(f"Using filter: {metadata_filter}")
            
            search_results = self.zilliz_client.search(
                collection_name=collection_name,
                **search_params
            )
            
            # Format the results
            formatted_results = []
            if search_results and len(search_results) > 0:
                for hit in search_results[0]:
                    entity = hit["entity"]
                    formatted_results.append({
                        "text": entity.get("text", ""),
                        "enriched_text": entity.get("enriched_text", ""),
                        "chunk_summary": entity.get("chunk_summary", ""),
                        "section_title": entity.get("section_title", ""),
                        "document_summary": entity.get("document_summary", ""),
                        "filename": entity.get("filename", ""),
                        "file_type": entity.get("file_type", ""),
                        "section_context": entity.get("section_context", ""),
                        "semantic_keywords": entity.get("semantic_keywords", []),
                        "score": 1.0 -  hit.get("distance", 0.0)
                    })

        except Exception as e:
            print(f"Error in search_chunks: {e}")
            print("Trying basic search without filtering...")
            
            # Fallback: try without filtering
            try:
                search_results = self.zilliz_client.search(
                    collection_name=collection_name,
                    data=[query_embedding],
                    limit=limit_r,
                    output_fields=output_fields,
                    anns_field= "vector",  # add: explicit vector field
                    search_params= {"metric_type": "COSINE", "params": {"ef": 256}},  # add: HNSW recall
                )
                
                formatted_results = []
                if search_results and len(search_results) > 0:
                    for hit in search_results[0]:
                        entity = hit["entity"]
                        formatted_results.append({
                        "text": entity.get("text", ""),
                        "enriched_text": entity.get("enriched_text", ""),
                        "chunk_summary": entity.get("chunk_summary", ""),
                        "section_title": entity.get("section_title", ""),
                        "document_summary": entity.get("document_summary", ""),
                        "filename": entity.get("filename", ""),
                        "file_type": entity.get("file_type", ""),
                        "section_context": entity.get("section_context", ""),
                        "semantic_keywords": entity.get("semantic_keywords", []),
                        "score": 1.0 -  hit.get("distance", 0.0)
                    })
            
            except Exception as fallback_error:
                print(f"Fallback search also failed: {fallback_error}")
                return []
            
        # RERANKING HERE (before returning):
        if RERANKER_ENABLED and self.reranker:
            formatted_results = self._rerank_results(query, formatted_results, top_k=limit)

        return formatted_results
   
    def hybrid_search_chunks_API(self, collection_name: str, query: str, limit: int = 5,
                                metadata_filter: Optional[str] = None) -> List[Dict[str, Any]]:
        """
        Hybrid search using the Zilliz hybrid search API with automatic fusion (RRF) of vector and BM25 results.
        Uses the BM25 function's sparse vectors for keyword matching.
        Note that the RRF scores are much lower (~0.008-0.033 range) than cosine similarity scores or the reranker scores and so are not directly comparable.

        """

        if RERANKER_ENABLED and self.reranker:
            limit_r = 2 * limit  # Fetch more for reranking
        else:
            limit_r = limit

        # Generate query embedding using YOUR SAME METHOD
        query_embedding = self.voyage_client.embed(
            [query],
            model=EMBEDDING_MODEL_NAME,
            input_type="query"
        ).embeddings[0]
            
        # Vector search request
        search_param_vector = {
            "data": [query_embedding],
            "anns_field": "vector",
            "param": {
                "metric_type": "COSINE",
                "params": {"ef": 256}  # HNSW search params
            },
            "limit": 20,
            "expr": None
        }
        vector_req = AnnSearchRequest(**search_param_vector)
        
        # BM25 search request on sparse vectors (auto-generated from enriched_text)
        search_param_bm25 = {
            "data": [query],  # Pass query as text, Milvus will convert via BM25 function
            "anns_field": "enriched_text_sparse",  # Use the sparse vector field
            "param": {
                "metric_type": "BM25",
                "params": {"drop_ratio_search": 0.2}
            },
            "limit": 20,
            "expr": metadata_filter
        }
        bm25_req = AnnSearchRequest(**search_param_bm25)
        
        rerank = Function(
        name="weight",
        input_field_names=[], # Must be an empty list
        function_type=FunctionType.RERANK,
        params={
            "reranker": "weighted", 
            "weights": [0.6, 0.4], #this weights need to go to top of module or into a config file
            "norm_score": True  # Optional
        }
    )

        # Hybrid search with RRF fusion
        results = self.zilliz_client.hybrid_search(
            collection_name=collection_name,
            reqs=[vector_req, bm25_req],
            #ranker=RRFRanker(k=60),   # RRF is reverse rank fusion. Can also use WeightedRanker which gives results comparable to cosine similarity
            ranker=rerank,  # Adjust weights for vector vs BM25. Weighting gives more interpretable scores comparable to cosine similarity
            limit=limit_r,
            output_fields=[
                "text", "enriched_text", "chunk_summary", "section_title", 
                "document_summary", "filename", "file_type", "section_context", 
                "semantic_keywords"
            ]
        )
        
        # Format results to match hybrid_search_chunks return type
        formatted_results = []
        hits = results[0] if results else []
        
        for hit in hits:
            # Access entity fields from the hit object
            entity = hit.entity if hasattr(hit, 'entity') else hit
            
            formatted_results.append({
                "text": entity.get("text", ""),
                "enriched_text": entity.get("enriched_text", ""),
                "chunk_summary": entity.get("chunk_summary", ""),
                "section_title": entity.get("section_title", ""),
                "document_summary": entity.get("document_summary", ""),
                "filename": entity.get("filename", ""),
                "file_type": entity.get("file_type", ""),
                "section_context": entity.get("section_context", ""),
                "semantic_keywords": entity.get("semantic_keywords", []),
                "score": hit.distance  # these are raw RRF scores
            })
        # RERANKING HERE (before returning):
        if RERANKER_ENABLED and self.reranker:
            formatted_results = self._rerank_results(query, formatted_results, top_k=limit)
        
        return formatted_results
    
    def _rerank_results(self, query: str, results: List[Dict[str, Any]], top_k: int = None) -> List[Dict[str, Any]]:
        """
        Rerank search results using Voyage reranker API.
        
        Args:
            query: Original search query
            results: List of search results with 'text' or 'enriched_text' fields
            top_k: Number of top results to return (default: keep all)
            
        Returns:
            Reranked list of results with updated scores
        """
        if not self.reranker or not results:
            return results
        
        try:
            # Extract documents for reranking (use enriched_text if available)
            documents = [
                result.get('enriched_text') or result.get('text', '')
                for result in results
            ]
            
            # Get reranker model from environment
            reranker_model = os.getenv("RERANKER_MODEL", "rerank-2.5-lite")
            
            # Call Voyage rerank API
            reranking = self.reranker.rerank(
                query=query,
                documents=documents,
                model=reranker_model,
                top_k=None  # Get all results, we'll slice later
            )
            
            # Map reranked scores back to original results
            # Voyage returns results sorted by relevance with original indices
            for rerank_result in reranking.results:
                idx = rerank_result.index
                results[idx]['rerank_score'] = rerank_result.relevance_score
                results[idx]['original_score'] = results[idx].get('score', 0.0)
            
            # Sort by rerank score (descending)
            reranked = sorted(results, key=lambda x: x.get('rerank_score', 0.0), reverse=True)
            
            # Return top_k if specified
            if top_k:
                reranked = reranked[:top_k]
            
            return reranked
            
        except Exception as e:
            print(f"Reranking failed: {e}. Returning original results.")
            return results
    
def example_usage():
    # Initialize the search tool with both Voyage, Milvus and Reranker clients.

    voyage_client = client_factory.create_voyage_client()
    milvus_client = client_factory.create_milvus_client()
    #reranker=None
    reranker = client_factory.create_reranker_client() if RERANKER_ENABLED else None
    search_tool = ZillizSearchTool(voyage_client, milvus_client, reranker)
    
    try:
        # Example searches using the new collection
        if True:
            print("\nSemantic Search Example:")
            results = search_tool.search_chunks(
                collection_name=COLLECTION_NAME,
                query="What are the maternity leave entitlements?",
                limit=5
            )
            for i, result in enumerate(results):
                print(f"Result {i+1}: {result['chunk_summary']}")
                print(f"Section: {result['section_title']}")
                print(f"From: {result['filename']}")
                print(f"Score: {result['score']:.4f}")
                print("---")
            
            print("\nFiltered Search Example:")
            results = search_tool.search_chunks(
                collection_name=COLLECTION_NAME,
                query="maternity policy requirements",
                limit=5,
                metadata_filter="file_type == \"pdf\""
            )
            for i, result in enumerate(results):
                print(f"Result {i+1}: {result['chunk_summary']}")
                print(f"Section: {result['section_title']}")
                print(f"From: {result['filename']} ({result['file_type']})")
                print(f"Score: {result['score']:.4f}")
                print("---")
            
            print("\nHybrid Search Example:")
            results = search_tool.hybrid_search_chunks_API(
                collection_name=COLLECTION_NAME,
                query="maternity leave duration weeks",
                limit=5
            )
            for i, result in enumerate(results):
                print(f"Result {i+1}: {result['chunk_summary']}")
                print(f"Section: {result['section_title']}")
                print(f"From: {result['filename']}")
                print(f"Keywords: {', '.join(result['semantic_keywords'][:5])}")
                print(f"Score: {result['score']:.4f}")
                print("---")
                
            # Demonstrate related chunks functionality
            if results:
                first_result = results[0]
                related_chunks = first_result.get('related_chunks', [])
                if related_chunks:
                    print("\nRelated Chunks for First Result:")
                    # Query for the related chunks
                    related_results = search_tool.zilliz_client.query(
                        collection_name=COLLECTION_NAME,
                        filter=f"chunk_id in {related_chunks}",
                        output_fields=["chunk_summary", "section_title", "filename"]
                    )
                    for i, rel in enumerate(related_results.get('data', [])):
                        print(f"Related {i+1}: {rel.get('chunk_summary', '')}")
                        print(f"Section: {rel.get('section_title', '')}")
                        print(f"From: {rel.get('filename', '')}")
                        print("---")
    
    except Exception as e:
        print(f"Error in main process: {e}")


def main() -> None:
    """Command-line interface for running semantic or hybrid searches.

    Usage:
        python Zilliz_src/search.py "what are reproductive health benefits" h --limit 10 --filter "file_type == 'pdf'"
        python Zilliz_src/search.py "maternity leave" s --limit 5
        python Zilliz_src/search.py "fertility benefits" h --limit 5 --verbose
    """

    parser = argparse.ArgumentParser(
        description="Run semantic (s) or hybrid (h) searches against the Zilliz collection."
    )
    parser.add_argument("query", help="Search query to execute. Wrap in quotes to preserve spaces.")
    parser.add_argument("mode", nargs="?", choices=["s", "h"], default="h", 
                       help="Search mode: 's' for semantic, 'h' for hybrid (default).")
    parser.add_argument("--limit", type=int, default=5, 
                       help="Number of results to return (default: 5).")
    parser.add_argument("--filter", dest="metadata_filter", 
                       help="Optional metadata filter expression to apply to the search.")
    parser.add_argument("--verbose", action="store_true", 
                       help="Show additional details like all keywords and section context.")

    args = parser.parse_args()

    # Initialize clients
    voyage_client = client_factory.create_voyage_client()
    milvus_client = client_factory.create_milvus_client()
    reranker = client_factory.create_reranker_client() if RERANKER_ENABLED else None
    search_tool = ZillizSearchTool(voyage_client, milvus_client, reranker)
    
    # Execute search based on mode
    if args.mode == "h":
        results = search_tool.hybrid_search_chunks_API(
            collection_name=COLLECTION_NAME,
            query=args.query,
            limit=args.limit,
            metadata_filter=args.metadata_filter,
        )
        search_type = "Hybrid"
    else:
        results = search_tool.search_chunks(
            collection_name=COLLECTION_NAME,
            query=args.query,
            limit=args.limit,
            metadata_filter=args.metadata_filter,
        )
        search_type = "Semantic"

    # Print header with reranking status
    rerank_status = " (WITH reranking)" if RERANKER_ENABLED and reranker else ""
    print(f"\n{'='*70}")
    print(f"{search_type} Search Results{rerank_status}")
    print(f"Query: '{args.query}'")
    print(f"Results: {len(results)}/{args.limit}")
    print(f"{'='*70}\n")
    
    if not results:
        print("No results found.")
        return

    # Print results
    for index, result in enumerate(results, start=1):
        print(f"Result {index}:")
        print(f"  Summary: {result.get('chunk_summary', 'N/A')}")
        
        # Section and document info
        section = result.get('section_title', '')
        if section:
            print(f"  Section: {section}")
        print(f"  Document: {result.get('filename', 'N/A')}")
        
        # Keywords (first 5 only unless verbose)
        keywords = result.get("semantic_keywords", [])
        if keywords:
            keywords_count = len(keywords) if args.verbose else min(5, len(keywords))
            keywords_display = ", ".join(keywords[:keywords_count])
            keywords_suffix = f" (showing {keywords_count}/{len(keywords)})" if len(keywords) > keywords_count else ""
            print(f"  Keywords: {keywords_display}{keywords_suffix}")
        
        # Score display - handle reranking appropriately
        if RERANKER_ENABLED and reranker and 'rerank_score' in result:
            # When reranked, show BOTH scores with clear labels
            print(f"  Rerank Score: {result.get('rerank_score', 0.0):.4f} (relevance)") #rerank score means after reranking
            print(f"  Retrieval Score: {result.get('score', 0.0):.4f} (original)") # score here means before reranking and could be either semantic similarity (cosine) score or the RRF/Weighted score (values much lower than for cosine metric) in the case of hybrid search
        else:
            # When not reranked, show only retrieval score
            print(f"  Score: {result.get('score', 0.0):.4f}")
        
        # Verbose mode: show additional fields
        if args.verbose:
            file_type = result.get('file_type', '')
            if file_type:
                print(f"  File Type: {file_type}")
            
            section_context = result.get('section_context', '')
            if section_context:
                # Truncate long context
                context_preview = section_context[:200] + "..." if len(section_context) > 200 else section_context
                print(f"  Context: {context_preview}")
        
        print(f"{'-'*70}\n")
    
    # Footer
    print(f"{'='*70}")
    if RERANKER_ENABLED and reranker:
        print("Note: Results are reordered by relevance (rerank score), not retrieval score.")
    print(f"{'='*70}\n")


if __name__ == "__main__":
    main()