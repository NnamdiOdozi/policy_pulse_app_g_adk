import os
import sys
import json
import datetime
from pathlib import Path
import time
from typing import List, Dict, Any, Optional, Tuple
from tqdm import tqdm

# For embeddings and vector database
import voyageai
from pymilvus import MilvusClient, DataType, Function, FunctionType, AnnSearchRequest, RRFRanker

# Load environment variables
from dotenv import load_dotenv
load_dotenv()

# Configuration
OPENAI_API_KEY = os.environ.get("OPENAI_API_KEY", "your-openai-api-key-here")  # For generating summaries
VOYAGE_API_KEY = os.environ.get("VOYAGE_API_KEY", "your-voyage-api-key-here")
ZILLIZ_CLOUD_URI = os.environ.get("ZILLIZ_CLOUD_URI", "https://in03-768dd5416cd6745.serverless.aws-eu-central-1.cloud.zilliz.com")
ZILLIZ_CLOUD_TOKEN = os.environ.get("ZILLIZ_API_KEY", "your-zilliz-token-here")
BATCH_SIZE = 100  # Adjust based on your data and API limits
COLLECTION_NAME = "WAE_2_docs_voyage_3_large"
EMBEDDING_DIM = 1024  # Voyage 3 Large dimension
EMBEDDING_MODEL_NAME = "voyage-3-large"
DOCS_DIRECTORY = "Temp_docs_list"  # Change to your actual directory path "Policy Pulse + AVE collab"

# === PATH SETUP ===
# UNUSUAL: We manipulate sys.path to allow imports from parent directories
current_dir = os.path.dirname(os.path.abspath(__file__))
project_root = os.path.join(current_dir, '..') 
sys.path.insert(0, os.path.abspath(project_root))

DOCS_DIRECTORY =  os.path.join(project_root, DOCS_DIRECTORY) 

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

BATCH_SIZE = 100
EMBEDDING_DIM = 1024

class ZillizMigrationTool:
    def __init__(self, voyage_api_key: str, zilliz_uri: str, zilliz_token: str, openai_api_key: str = None):
        """
        Initialize the migration tool with API keys and connection details. It  creates an instance of the DocumentProcessor class to load docs, chunk them and enrich them
        
        Args:
            voyage_api_key: API key for Voyage AI
            zilliz_uri: URI for Zilliz Cloud instance
            zilliz_token: Token for Zilliz Cloud authentication
            openai_api_key: Optional API key for OpenAI (for summarization)
        """
        self.voyage_client = voyageai.Client(api_key=voyage_api_key)
        self.zilliz_client = MilvusClient(
            uri=zilliz_uri,
            token=zilliz_token
        )
        
        self.document_processor = None
        if openai_api_key:
            from Zilliz_src.document_processor import DocumentProcessor  # Adjust import as needed
            self.document_processor = DocumentProcessor(openai_api_key)
        
        # Create logs directory if it doesn't exist
        self.logs_dir = Path("embedding_logs")
        self.logs_dir.mkdir(exist_ok=True)
        
        # Create single log file for this script run
        timestamp = datetime.datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
        self.current_log_file = self.logs_dir / f"chunks_log_{timestamp}.json"
        self.log_data = {
            "script_run": {
            "timestamp": datetime.datetime.now().isoformat(),
            "voyage_model": EMBEDDING_MODEL_NAME,
            "embedding_dimension": EMBEDDING_DIM
            },
            "chunks": []
        }
        
        print("Clients initialized successfully")

    def create_collection(self, collection_name: str, dimension: int = EMBEDDING_DIM, drop_if_exists: bool = False):
        """
        Create the collection with TEXT_MATCH support, or reuse an existing one.
        - Will NOT drop if the collection exists unless drop_if_exists=True
        - Builds HNSW index for the vector field and INVERTED indexes for text fields
        """
        client = self.zilliz_client

        # 1) If it already exists, keep it (so you can add new vectors)
        if client.has_collection(collection_name):
            if drop_if_exists:
                print(f"Collection '{collection_name}' exists. Dropping as requested...")
                client.drop_collection(collection_name)
            else:
                print(f"Collection '{collection_name}' already exists. Leaving as-is and loading.")
                client.load_collection(collection_name)
                return

        # 2) Define schema (MilvusClient style)
        schema = MilvusClient.create_schema(
            auto_id=False,
            enable_dynamic_field=False,
            description="Documents with TEXT_MATCH support",
        )

        # Primary key as VARCHAR (so you can keep your string ids)
        schema.add_field(
            field_name="id",
            datatype=DataType.VARCHAR,
            max_length=200,
            is_primary=True,
        )

        # Main text field with full-text enabled
        schema.add_field(
            field_name="text",
            datatype=DataType.VARCHAR,
            max_length=5000,
            enable_analyzer=True,
            enable_match=True,
            analyzer_params={"type": "english"},
        )
        # ENRICHED_TEXT: Enriched text used for all search operations
        # Contains raw text PLUS metadata context (summary, keywords, etc.)
        # Used for: 
        #   1. Vector embedding generation (semantic search)
        #   2. Inverted index TEXT_MATCH (keyword/hybrid search)
        #   3. LLM context when answering queries
        # NOT updated when metadata changes - accepts staleness as trade-off
        # This creates consistency: same content used for both vector and keyword search
        schema.add_field(
            field_name="enriched_text",
            datatype=DataType.VARCHAR,
            max_length=10000,
            enable_analyzer=True,
            enable_match=True,
            analyzer_params={"type": "english"},
        )

        # Sparse vector field for BM25 (auto-generated from enriched_text)
        schema.add_field(
            field_name="enriched_text_sparse",
            datatype=DataType.SPARSE_FLOAT_VECTOR,
            description="BM25 sparse vectors auto-generated from enriched_text"
        )

        # Other metadata fields
        schema.add_field("filename", datatype=DataType.VARCHAR, max_length=256)
        schema.add_field("file_type", datatype=DataType.VARCHAR, max_length=20)
        schema.add_field("file_path", datatype=DataType.VARCHAR, max_length=512)
        schema.add_field("file_hash", datatype=DataType.VARCHAR, max_length=64)  
        schema.add_field("file_size", datatype=DataType.INT64)  #  - File size in bytes
        schema.add_field("indexed_at", datatype=DataType.VARCHAR, max_length=30)
        schema.add_field("chunk_id", datatype=DataType.VARCHAR, max_length=200)

        schema.add_field(
            field_name="chunk_summary",
            datatype=DataType.VARCHAR,
            max_length=512,
            enable_analyzer=True,
            enable_match=True,
        )

        schema.add_field(
            field_name="section_title",
            datatype=DataType.VARCHAR,
            max_length=256,
            enable_analyzer=True,
            enable_match=True,
        )
        
        schema.add_field("section_context", datatype=DataType.VARCHAR, max_length=256)
        schema.add_field("document_summary", datatype=DataType.VARCHAR, max_length=256)

        # Structured data
        schema.add_field("semantic_keywords", datatype=DataType.JSON)
        schema.add_field("related_chunks", datatype=DataType.JSON)
        schema.add_field("cross_references", datatype=DataType.JSON)
        
        # NEW: Flattened keywords for TEXT_MATCH
        schema.add_field(
            field_name="keywords_text",
            datatype=DataType.VARCHAR,
            max_length=1000,
            enable_analyzer=True,
            enable_match=True,
        )

        # Dense vector field
        schema.add_field("vector", datatype=DataType.FLOAT_VECTOR, dim=dimension)

        # Define BM25 function to auto-generate sparse vectors from enriched_text
        bm25_function = Function(
            name="enriched_text_bm25",
            input_field_names=["enriched_text"],  # Takes enriched_text as input
            output_field_names=["enriched_text_sparse"],  # Outputs to sparse field
            function_type=FunctionType.BM25,
        )
        schema.add_function(bm25_function)

        # 3) Create collection
        client.create_collection(collection_name=collection_name, schema=schema)

        # 4) Build indexes (MilvusClient requires IndexParams object)
        index_params = MilvusClient.prepare_index_params()

        # Vector ANN index (HNSW)
        index_params.add_index(
            field_name="vector",
            index_type="HNSW",
            metric_type="COSINE",
            index_name="vector_hnsw",
            params={"M": 16, "efConstruction": 200},
        )

        # BM25 sparse vector index
        index_params.add_index(
            field_name="enriched_text_sparse",
            index_type="SPARSE_INVERTED_INDEX",
            metric_type="BM25",
            index_name="enriched_text_sparse_bm25"
        )


        # Inverted indexes for TEXT_MATCH-capable fields
        index_params.add_index(field_name="text", index_type="INVERTED", index_name="text_inverted")
        index_params.add_index(field_name="enriched_text", index_type="INVERTED", index_name="enriched_text_inverted")
        index_params.add_index(field_name="chunk_summary", index_type="INVERTED", index_name="chunk_summary_inverted")
        index_params.add_index(field_name="section_title", index_type="INVERTED", index_name="section_title_inverted")
        index_params.add_index(field_name="keywords_text", index_type="INVERTED", index_name="keywords_text_inverted")

        client.create_index(collection_name=collection_name, index_params=index_params)

        # 5) Load for use
        client.load_collection(collection_name)

        print(f"Collection '{collection_name}' created & loaded (TEXT_MATCH + HNSW ready).")

    def _create_enriched_embedding_text(self, chunk: Dict[str, Any]) -> str:
        """
        Create enriched text for embedding that includes metadata.
        
        Args:
            chunk: Chunk dictionary with all metadata
            
        Returns:
            Enriched text string for embedding
        """
        # Join semantic keywords into a readable string
        keywords_str = ", ".join(chunk.get("semantic_keywords", [])[:8])  # Limit to top 8
        
        # Create enriched embedding text
        enriched_text = f"""{chunk['text']}

Summary: {chunk.get('chunk_summary', '')}
Context: {chunk.get('section_context', '')}
Document: {chunk.get('document_summary', '')}
Keywords: {keywords_str}
File Type: {chunk.get('file_type', '').upper()}
Source: {chunk.get('filename', '')}"""

        return enriched_text.strip()

    def _log_chunk(self, chunk: Dict[str, Any], enriched_text: str, embedding: List[float]):
        """
        Add chunk processing details to the current log.
        
        Args:
            chunk: Original chunk data
            enriched_text: The enriched text that was embedded
            embedding: The generated embedding vector
        """
        # Add chunk data to the log
        chunk_log = {
            "chunk_id": chunk.get("chunk_id", ""),
            "metadata": {
                "id": chunk.get("id", ""),
                "filename": chunk.get("filename", ""),
                "file_type": chunk.get("file_type", ""),
                "file_path": chunk.get("file_path", ""),
                "indexed_at": chunk.get("indexed_at", ""),
                "section_title": chunk.get("section_title", ""),
                "chunk_summary": chunk.get("chunk_summary", ""),
                "section_context": chunk.get("section_context", ""),
                "document_summary": chunk.get("document_summary", ""),
                "semantic_keywords": chunk.get("semantic_keywords", []),
                "related_chunks": chunk.get("related_chunks", []),
                "cross_references": chunk.get("cross_references", [])
            },
            "original_text": chunk.get("text", ""),
            "enriched_embedding_text": enriched_text,
            "embedding_stats": {
                "original_length": len(chunk.get("text", "")),
                "enriched_length": len(enriched_text),
                "enrichment_ratio": round(len(enriched_text) / max(len(chunk.get("text", "")), 1), 2),
                "embedding_dimensions": len(embedding),
                "keywords_count": len(chunk.get("semantic_keywords", [])),
                "related_chunks_count": len(chunk.get("related_chunks", []))
            }
        }
        
        # Add to the main log data
        self.log_data["chunks"].append(chunk_log)

    def _save_log_file(self):
        """
        Save the complete log file for this script run.
        """
        try:
            # Add run summary
            self.log_data["script_run"]["total_chunks"] = len(self.log_data["chunks"])
            self.log_data["script_run"]["completed_at"] = datetime.datetime.now().isoformat()
            
            # Calculate summary stats
            if self.log_data["chunks"]:
                enrichment_ratios = [chunk["embedding_stats"]["enrichment_ratio"] for chunk in self.log_data["chunks"]]
                self.log_data["script_run"]["summary_stats"] = {
                    "avg_enrichment_ratio": round(sum(enrichment_ratios) / len(enrichment_ratios), 2),
                    "min_enrichment_ratio": min(enrichment_ratios),
                    "max_enrichment_ratio": max(enrichment_ratios),
                    "files_processed": len(set(chunk["metadata"]["filename"] for chunk in self.log_data["chunks"]))
                }
            
            with open(self.current_log_file, 'w', encoding='utf-8') as f:
                json.dump(self.log_data, f, indent=2, ensure_ascii=False)
                
            print(f"Complete processing log saved to: {self.current_log_file}")
            return True
            
        except Exception as e:
            print(f"Warning: Could not save processing log: {e}")
            return False
    
    def generate_embeddings(self, texts: List[str], show_progress: bool = True) -> List[List[float]]:
        """
        Generate embeddings for a list of texts using Voyage 3 Large model.
        
        Args:
            texts: List of text strings to embed
            show_progress: Whether to show a progress bar
        
        Returns:
            List of embeddings as float vectors
        """
        
        
        # Process in smaller batches to avoid API limits
        all_embeddings = []
        
        # Create batches
        batches = [texts[i:i + BATCH_SIZE] for i in range(0, len(texts), BATCH_SIZE)]
        
        if show_progress:
            batches = tqdm(batches, desc="Generating embeddings")
        
        for batch in batches:
            try:
                # Generate embeddings using Voyage 3 Large model
                response = self.voyage_client.embed(
                    batch, 
                    model=EMBEDDING_MODEL_NAME, 
                    input_type="document",
                    output_dimension=1024
                )
                
                # Add the embeddings to our results
                all_embeddings.extend(response.embeddings)
                
                # Avoid rate limiting
                if len(batches) > 1:
                    time.sleep(0.5)
                    
            except Exception as e:
                print(f"Error generating embeddings: {e}")
                # Return empty embeddings for this batch to maintain alignment
                all_embeddings.extend([[0.0] * EMBEDDING_DIM] * len(batch))
        
        return all_embeddings
    
    def process_directory_and_insert(self, collection_name: str, directory_path: str):
        """
        Process all documents in a directory and insert them into Zilliz.
        
        Args:
            collection_name: Name of the collection to insert into
            directory_path: Path to directory containing documents
        """
        if not self.document_processor:
            raise ValueError("Document processor not initialized. Please provide an OpenAI API key.")
        
        # Process all documents in the directory
        chunks = self.document_processor.process_directory(directory_path)
        
        # Create collection if it doesn't exist
        if not self.zilliz_client.has_collection(collection_name):
            self.create_collection(collection_name, 1024)
        
        # Insert chunks into collection
        self.insert_chunks(collection_name, chunks)
        
        return chunks
    
    def _prepare_chunk_data(self, chunk, embedding, enriched_text):
        """
        Prepare chunk data for Zilliz insertion with dual text field, with ID coercion and field validation.
        
        Returns:
            chunk_data dict with:
            - text: Raw chunk text (display only)
            - enriched_text: Enriched version (search + LLM context)
            - vector: Embedding from enriched_text
            
        Note: The embedding is generated from enriched_text, ensuring 
        consistency between vector and keyword search operations.
        """

        # Create flattened keywords text for TEXT_MATCH
        keywords_text = ", ".join(chunk.get("semantic_keywords", []))
        
        chunk_data = {
            "id": chunk["id"],  # Keep as string now that we have VARCHAR primary key
            "text": chunk["text"],
            "enriched_text": enriched_text,
            "filename": chunk["filename"],
            "file_type": chunk.get("file_type", ""),
            "file_path": chunk.get("file_path", ""),
            "file_hash": chunk.get("file_hash", ""),   
            "file_size": chunk.get("file_size", 0),   
            "indexed_at": chunk.get("indexed_at", ""),
            "chunk_id": chunk.get("chunk_id", ""),
            "section_title": chunk.get("section_title", ""),
            "chunk_summary": chunk.get("chunk_summary", ""),
            "section_context": chunk.get("section_context", ""),
            "document_summary": chunk.get("document_summary", ""),
            "semantic_keywords": chunk.get("semantic_keywords", []),
            "related_chunks": [],  # Simplified: remove complex cross-doc analysis
            "cross_references": chunk.get("cross_references", []),
            "keywords_text": keywords_text,  # NEW: flattened for TEXT_MATCH
            "vector": embedding
        }
            
        return chunk_data
    
    def insert_chunks(self, collection_name: str, chunks: List[Dict[str, Any]], 
                     show_progress: bool = True):
        """
        Insert chunks with enriched embeddings and logging.
        """
        BATCH_SIZE = 100
        
        # Create enriched texts for embedding
        print("Creating enriched embedding texts...")
        enriched_texts = []
        for chunk in chunks:
            enriched_text = self._create_enriched_embedding_text(chunk)
            enriched_texts.append(enriched_text)
        
        print(f"Enhanced {len(chunks)} chunks with metadata")
        print(f"Average enrichment: {sum(len(et) for et in enriched_texts) // len(enriched_texts)} chars")
        
        # Generate embeddings on enriched text (not raw text)
        # This ensures vector search operates on the same enriched content
        # that keyword search will use via inverted index
        embeddings = self.generate_embeddings(enriched_texts, show_progress)
        
        # Log chunk processing details
        print("Logging chunk processing details...")
        for i, (chunk, enriched_text, embedding) in enumerate(zip(chunks, enriched_texts, embeddings)):
            self._log_chunk(chunk, enriched_text, embedding)
            
        print(f"Logged {len(chunks)} chunks for this run")
        
        # Batch all three lists together for insertion
        # Each chunk needs: raw text (display), enriched text (search), embedding (vector)
        batches = [(chunks[i:i + BATCH_SIZE], 
                    embeddings[i:i + BATCH_SIZE],
                    enriched_texts[i:i + BATCH_SIZE]) 
                   for i in range(0, len(chunks), BATCH_SIZE)]
        
        if show_progress:
            batches = tqdm(batches, desc="Inserting chunks")
        
        for batch_chunks, batch_embeddings, batch_enriched_texts in batches:
            try:
                insert_data = []
                for i, chunk in enumerate(batch_chunks):
                    chunk_data = self._prepare_chunk_data(chunk, batch_embeddings[i], batch_enriched_texts[i])
                    insert_data.append(chunk_data)
                
                # Insert the batch - I changed this to upsert rather than insert so that new chunks with same id would overwrite older chunks
                self.zilliz_client.upsert(
                    collection_name=collection_name,
                    data=insert_data
                )
                
            except Exception as e:
                print(f"Error inserting batch: {e}")
            
            # Avoid rate limiting
            if len(batches) > 1:
                time.sleep(0.2)
        
        # Load the collection to make it available for search
        self.zilliz_client.load_collection(collection_name)
        print(f"Inserted {len(chunks)} chunks into collection '{collection_name}'")
        
        # Save the complete log file
        self._save_log_file()

    def get_file_hash(self, collection_name: str, file_path: str) -> Optional[str]:
        """
        Get the stored hash for a file by querying any of its chunks.
        
        Args:
            collection_name: Collection to query
            file_path: Full path to the file
            
        Returns:
            SHA-256 hash string or None if file not found
        """
        try:
        # Escape backslashes for Windows paths in filter expression
            escaped_path = file_path.replace("\\", "\\\\")
            
            # Query for any chunk from this file
            results = self.zilliz_client.query(
                collection_name=collection_name,
                filter=f'file_path == "{escaped_path}"',
                output_fields=["file_hash"],
                limit=1
            )
            
            if results and len(results) > 0:
                return results[0].get("file_hash")
            return None
            
        except Exception as e:
            print(f"Error querying file hash: {e}")
            return None
    
    def update_chunks_metadata(self, collection_name: str, old_file_path: str, 
                          new_filename: str, new_file_path: str):
        """
        Update filename and file_path in all chunks when file is renamed.
        Used when content hasn't changed (same hash).

        Does NOT update:
        - text: Kept as original chunk text for display
        - enriched_text: Intentionally left with original metadata
        - vector: Represents the original enriched content
        
        Rationale: The vector embedding was generated from enriched_text containing
        the original filename. Changing enriched_text would create inconsistency with
        the embedding. Re-embedding would be expensive and typically unnecessary since
        the actual content hasn't changed.
        
        This means enriched_text may contain stale metadata (e.g., old filename), but
        this is acceptable because:
        1. Semantic search (vector) still works correctly on content
        2. Keyword searches on metadata use structured fields, not enriched_text
        3. Raw text field has correct metadata for display
        4. Metadata staleness doesn't affect the core meaning of the content


        """
        try:
            # Escape backslashes for Windows paths
            escaped_old_path = old_file_path.replace("\\", "\\\\")
            
            # Query all chunks for the old file path - GET ONLY ID FIRST
            chunks = self.zilliz_client.query(
                collection_name=collection_name,
                filter=f'file_path == "{escaped_old_path}"',
                output_fields=["id"],
                limit=10000
            )
            
            if not chunks:
                print(f"No chunks found for {old_file_path}")
                return
            
            print(f"Found {len(chunks)} chunks to update for rename")
            
            # Deduplicate by ID just in case
            unique_ids = list(set(chunk["id"] for chunk in chunks))
            print(f"Unique IDs: {len(unique_ids)}")
            
            if len(unique_ids) != len(chunks):
                print(f"⚠️  WARNING: Found {len(chunks) - len(unique_ids)} duplicate IDs in query!")
            
            # Now fetch full data for each unique ID
            for i, chunk_id in enumerate(unique_ids):
                # Get SPECIFIC fields (not "*")
                full_data = self.zilliz_client.query(
                    collection_name=collection_name,
                    filter=f'id == "{chunk_id}"',
                    output_fields=[
                        "id", "text", "filename", "file_type", "file_path", 
                        "file_hash", "file_size", "indexed_at", "chunk_id",
                        "section_title", "chunk_summary", "section_context",
                        "document_summary", "semantic_keywords", "related_chunks",
                        "cross_references", "keywords_text", "vector"
                    ],
                    limit=1
                )
                
                if not full_data:
                    print(f"⚠️  Could not fetch data for chunk: {chunk_id}")
                    continue
                    
                updated_chunk = full_data[0]
                
                # Update ONLY the fields that changed
                updated_chunk["filename"] = new_filename
                updated_chunk["file_path"] = new_file_path
                # file_hash stays the same (content unchanged)
                
                if i < 3:  # Log first 3
                    print(f"  Updating chunk {i+1}/{len(unique_ids)}: {chunk_id}")
                    print(f"    Old filename: {updated_chunk.get('filename')}")
                    print(f"    New filename: {new_filename}")
                
                # CRITICAL: Upsert with the SAME ID to overwrite
                try:
                    self.zilliz_client.upsert(
                        collection_name=collection_name,
                        data=[updated_chunk]
                    )
                except Exception as e:
                    print(f"⚠️  Error upserting chunk {chunk_id}: {e}")
            
            print(f"✅ Updated {len(unique_ids)} chunks with new filename: {new_filename}")
            
        except Exception as e:
            print(f"❌ Error updating chunk metadata: {e}")
            import traceback
            traceback.print_exc()

    def search_chunks(self, collection_name: str, query: str, limit: int = 5, 
                 metadata_filter: Optional[str] = None) -> List[Dict[str, Any]]:
        """
        Semantic search using vector embeddings generated from enriched text.
        
        Returns both text fields:
        - text: Clean chunk for user display
        - enriched_text: Full context for LLM reasoning
        
        The vector search operates on embeddings generated from enriched_text,
        ensuring semantic similarity includes metadata context.
        """
        try:
            # Generate embedding for the query
            query_embedding = self.voyage_client.embed(
                [query], 
                model=EMBEDDING_MODEL_NAME, 
                input_type="query",
                output_dimension=1024
            ).embeddings[0]
            
            # Define output fields - ensure they match your schema
            output_fields = [
                "text", "enriched_text", "chunk_summary", "section_title", "document_summary",
                "filename", "file_type", "section_context", "semantic_keywords"
            ]
            
            # Perform the search
            search_params = {
                "data": [query_embedding],
                "limit": limit,
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
                        "chunk_summary": entity.get("chunk_summary", ""),
                        "section_title": entity.get("section_title", ""),
                        "document_summary": entity.get("document_summary", ""),
                        "filename": entity.get("filename", ""),
                        "file_type": entity.get("file_type", ""),
                        "section_context": entity.get("section_context", ""),
                        "semantic_keywords": entity.get("semantic_keywords", []),
                        "score": 1.0 -  hit.get("distance", 0.0)
                    })
            
            return formatted_results
            
        except Exception as e:
            print(f"Error in search_chunks: {e}")
            print("Trying basic search without filtering...")
            
            # Fallback: try without filtering
            try:
                search_results = self.zilliz_client.search(
                    collection_name=collection_name,
                    data=[query_embedding],
                    limit=limit,
                    output_fields=["text", "chunk_summary", "filename"],
                    anns_field= "vector",  # add: explicit vector field
                    search_params= {"metric_type": "COSINE", "params": {"ef": 256}},  # add: HNSW recall
                )
                
                formatted_results = []
                if search_results and len(search_results) > 0:
                    for hit in search_results[0]:
                        entity = hit["entity"]
                        formatted_results.append({
                            "text": entity.get("text", ""),
                            "chunk_summary": entity.get("chunk_summary", ""),
                            "filename": entity.get("filename", ""),
                            "score": 1.0 - hit.get("distance", 0.0)
                        })
                
                return formatted_results
            except Exception as fallback_error:
                print(f"Fallback search also failed: {fallback_error}")
                return []

    
    def hybrid_search_chunks(self, collection_name: str, query: str, limit: int = 5,
                            metadata_filter: Optional[str] = None) -> List[Dict[str, Any]]:
        """
        Manual Hybrid search combining vector similarity and keyword matching on enriched content.
        
        Keyword matching via TEXT_MATCH searches the enriched_text field, which includes:
        - Original chunk text
        - Chunk summary
        - Section context
        - Document summary
        - Semantic keywords
        
        This creates consistency: both vector and keyword search operate on the same
        enriched content, providing complementary retrieval methods over full context.
        
        Note: Keywords can match metadata even if not in chunk text itself - generally
        desirable for policy analysis where document context matters.
        """
        # Extract potential keywords from the query
        keywords = [word for word in query.split() if len(word) > 3]
        
        # Create text match filters for all searchable fields
        text_match_filters = []
        for keyword in keywords:
            text_match_filters.append(f'TEXT_MATCH(text, "{keyword}")')
            text_match_filters.append(f'TEXT_MATCH(chunk_summary, "{keyword}")')
            text_match_filters.append(f'TEXT_MATCH(section_title, "{keyword}")')
            text_match_filters.append(f'TEXT_MATCH(keywords_text, "{keyword}")')  # NEW: include keywords
        
        # Combine with metadata filter if provided
        combined_filter = " OR ".join(text_match_filters)
        if metadata_filter:
            if combined_filter:
                combined_filter = f"({combined_filter}) AND ({metadata_filter})"
            else:
                combined_filter = metadata_filter
        
        try:
            # First attempt: try with TEXT_MATCH filtering
            if combined_filter:
                print("Attempting hybrid search with TEXT_MATCH...")
                results = self.search_chunks(
                    collection_name=collection_name,
                    query=query,
                    limit=limit,
                    metadata_filter=combined_filter
                )
                
                # If we got results, return them
                if results:
                    print(f"Found {len(results)} results with hybrid search")
                    return results
            
        except Exception as e:
            if "text match operation" in str(e) or "TEXT_MATCH" in str(e):
                print("TEXT_MATCH not supported, falling back to semantic search...")
            else:
                print(f"Hybrid search error: {e}")
        
        # Fallback: standard semantic search
        print("Using semantic search fallback...")
        return self.search_chunks(
            collection_name=collection_name,
            query=query,
            limit=limit
        )
    
    def hybrid_search_chunks_API(self, collection_name: str, query: str, limit: int = 5,
                                metadata_filter: Optional[str] = None) -> List[Dict[str, Any]]:
        """
        Hybrid search using the Zilliz hybrid search API with automatic fusion of vector and BM25 results.
        Uses the BM25 function's sparse vectors for keyword matching.
        """
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
        
        # Hybrid search with RRF fusion
        results = self.zilliz_client.hybrid_search(
            collection_name=collection_name,
            reqs=[vector_req, bm25_req],
            ranker=RRFRanker(k=60),  
            limit=limit,
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
                "score": 1.0 - hit.distance if hasattr(hit, 'distance') else hit.get('score', 0.0)
            })
        
        return formatted_results
        
def main():
    # Initialize the migration tool with both Voyage and OpenAI API keys
    migration_tool = ZillizMigrationTool(
        voyage_api_key=VOYAGE_API_KEY,
        zilliz_uri=ZILLIZ_CLOUD_URI,
        zilliz_token=ZILLIZ_CLOUD_TOKEN,
        openai_api_key=OPENAI_API_KEY
    )
    
    # Test raw chunk count first
    raw_count = migration_tool.document_processor.test_raw_chunk_count(DOCS_DIRECTORY)

    # Process all documents in the directory and insert into Zilliz
    try:
        #chunks = {"test": "test"} #remove this line once done with testing
        chunks = migration_tool.process_directory_and_insert(
            collection_name=COLLECTION_NAME,
            directory_path=DOCS_DIRECTORY
        )
        print(f"Successfully processed and inserted {len(chunks)} chunks")

        print(f"\n=== COMPARISON ===")
        print(f"Raw chunks (no LLM): {raw_count}")
        print(f"Processed chunks: {len(chunks)}")
        print(f"Chunks lost: {raw_count - len(chunks)}")

        
        # Example searches using the new collection
        if chunks:
            print("\nSemantic Search Example:")
            results = migration_tool.search_chunks(
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
            results = migration_tool.search_chunks(
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
            results = migration_tool.hybrid_search_chunks_API(
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
                    related_results = migration_tool.zilliz_client.query(
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

if __name__ == "__main__":
    main()
    