import os
import json
import numpy as np
import datetime
from pathlib import Path
import time
from typing import List, Dict, Any, Optional, Tuple
from tqdm import tqdm

# For embeddings and vector database
import voyageai
from pymilvus import MilvusClient, DataType

# For document processing
import docx
import pdfplumber
import re
from langchain_openai import ChatOpenAI
from langchain.text_splitter import RecursiveCharacterTextSplitter

# Configuration
VOYAGE_API_KEY = os.environ.get("VOYAGE_API_KEY", "your-voyage-api-key-here")
ZILLIZ_CLOUD_URI = os.environ.get("ZILLIZ_CLOUD_URI", "https://in03-768dd5416cd6745.serverless.aws-eu-central-1.cloud.zilliz.com")
ZILLIZ_CLOUD_TOKEN = os.environ.get("ZILLIZ_API_KEY", "your-zilliz-token-here")
OPENAI_API_KEY = os.environ.get("OPENAI_API_KEY", "your-openai-api-key-here")  # For generating summaries
BATCH_SIZE = 100  # Adjust based on your data and API limits
COLLECTION_NAME = "documents_voyage_3_large"
EMBEDDING_DIM = 1024  # Voyage 3 Large dimension
DOCS_DIRECTORY = "Temp"  # Change to your actual directory path PolicyPulse + AVE collab


import hashlib
from typing import Any, List

def _to_int64_pk(x: Any, *, salt: str = "") -> int:
    """
    Convert any stable string-like ID to a signed 63-bit int deterministically.
    Keeps your existing 'id' field (INT64 PK) without changing schema.
    """
    if isinstance(x, int):
        return x
    s = str(x) + salt
    # sha1 -> 160-bit -> take lower 63 bits to avoid negative overflow in signed int64
    v = int(hashlib.sha1(s.encode("utf-8")).hexdigest(), 16) & ((1 << 63) - 1)
    return v

def _build_textmatch_filter_if_supported(client, collection_name: str, keywords: List[str], field: str = "text") -> str | None:
    """
    Only emits TEXT_MATCH() if the 'field' is a VARCHAR with analyzer+match enabled.
    Otherwise returns None so your hybrid search won’t error out.
    """
    try:
        desc = client.describe_collection(collection_name)
        # MilvusClient describe schema shape: desc["schema"]["fields"] list of dicts
        fields = {f["name"]: f for f in desc["schema"]["fields"]}
        f = fields.get(field)
        if not f:
            return None
        # DataType.VARCHAR shows as "VarChar" or similar depending on client;
        # enable_analyzer / enable_match flags exist only when text-match is allowed.
        if (f.get("data_type", "").lower() in ("varchar", "var_char", "string")
            and f.get("enable_analyzer") is True
            and f.get("enable_match") is True):
            clauses = [f'TEXT_MATCH({field}, "{k}")' for k in keywords if k]
            return " OR ".join(clauses) if clauses else None
        return None
    except Exception:
        # Keep this minimal: if introspection fails, just skip TEXT_MATCH
        return None


# Now include the DocumentProcessor class
class DocumentProcessor:
    """Process documents into chunks with rich metadata."""
    
    def __init__(self, openai_api_key: str):
        """
        Initialize the document processor.
        
        Args:
            openai_api_key: API key for OpenAI (used for generating summaries)
        """
        self.text_splitter = RecursiveCharacterTextSplitter(
            chunk_size=2000,
            chunk_overlap=400,
            length_function=len,
        )
        
        # Initialize LLM for generating summaries
        self.llm = ChatOpenAI(
            model="gpt-4o-mini",
            temperature=0.0,
            api_key=openai_api_key
        )
    
    def extract_text_from_file(self, file_path: Path) -> str:
        """
        Extract text content from different file types.
        
        Args:
            file_path: Path to the document file
            
        Returns:
            Extracted text content
        """
        file_extension = file_path.suffix.lower()
        
        if file_extension == '.pdf':
            return self._extract_from_pdf(file_path)
        elif file_extension == '.docx':
            return self._extract_from_docx(file_path)
        elif file_extension in ['.txt', '.md']:
            return self._extract_from_text(file_path)
        else:
            print(f"Unsupported file type: {file_extension}")
            return ""
    
    def _extract_from_pdf(self, file_path: Path) -> str:
        """Extract text from PDF files."""
        text = ""
        try:
            with pdfplumber.open(file_path) as pdf:
                for page in pdf.pages:
                    page_text = page.extract_text() or ""
                    text += page_text + "\n\n"
            return text
        except Exception as e:
            print(f"Error extracting text from PDF {file_path}: {e}")
            return ""
    
    def _extract_from_docx(self, file_path: Path) -> str:
        """Extract text from DOCX files."""
        try:
            doc = docx.Document(file_path)
            return "\n\n".join([paragraph.text for paragraph in doc.paragraphs])
        except Exception as e:
            print(f"Error extracting text from DOCX {file_path}: {e}")
            return ""
    
    def _extract_from_text(self, file_path: Path) -> str:
        """Extract text from TXT or MD files."""
        try:
            with open(file_path, 'r', encoding='utf-8') as file:
                return file.read()
        except Exception as e:
            print(f"Error extracting text from text file {file_path}: {e}")
            return ""
    
    def extract_section_title(self, text: str) -> str:
        """
        Extract a section title from the chunk text.
        
        Args:
            text: The chunk text
            
        Returns:
            Extracted section title or default title
        """
        # Look for common section title patterns
        section_patterns = [
            r'^(?:Section|SECTION)\s+\d+[\.:]\s*(.*?)(?:\n|$)',  # Section X: Title
            r'^(?:\d+\.)+\s*(.*?)(?:\n|$)',  # 1.2.3 Title
            r'^[A-Z][A-Z\s]+(?:\n|$)',  # ALL CAPS TITLE
            r'^(?:Article|ARTICLE)\s+\d+[\.:]\s*(.*?)(?:\n|$)',  # Article X: Title
        ]
        
        for pattern in section_patterns:
            match = re.search(pattern, text, re.MULTILINE)
            if match:
                return match.group(1).strip() if len(match.groups()) > 0 else match.group(0).strip()
        
        # Fallback: use first line if it's short enough to be a title
        lines = text.split('\n')
        if lines and len(lines[0]) < 100:
            return lines[0].strip()
        
        return "Untitled Section"
    
    def generate_chunk_summary(self, text: str) -> str:
        """
        Generate a summary for a chunk using LLM.
        
        Args:
            text: The chunk text
            
        Returns:
            Generated summary in the format "Label - brief summary sentence"
        """
        try:
            prompt = f"""
            Create a concise label that captures the essence of this text chunk, followed by a dash, 
            and then a summary sentence of no more than 12 words.
            
            Format example: "Employment Benefits - Outlines available health insurance and retirement options."
            
            Text chunk:
            {text[:1500]}  # Limit input to avoid token limits
            
            Label - Summary:
            """
            
            response = self.llm.invoke(prompt)
            summary = response.content.strip()
            
            # Ensure it has the label - summary format
            if " - " not in summary:
                parts = summary.split(" ", 3)
                if len(parts) >= 3:
                    summary = f"{parts[0]} {parts[1]} - {' '.join(parts[2:])}"
                else:
                    summary = f"Section Summary - {summary}"
            
            return summary
        except Exception as e:
            print(f"Error generating summary: {e}")
            return "Document Section - Contains policy information."
    
    def extract_keywords(self, text: str) -> List[str]:
        """
        Extract semantic keywords from the chunk text.
        
        Args:
            text: The chunk text
            
        Returns:
            List of extracted keywords
        """
        # Simple rule-based keyword extraction
        # In a production system, you might use NLP techniques or LLMs for this
        words = re.findall(r'\b[a-zA-Z]{4,}\b', text.lower())
        word_counts = {}
        
        for word in words:
            if word not in ['that', 'this', 'with', 'from', 'have', 'were', 'they', 'their']:
                word_counts[word] = word_counts.get(word, 0) + 1
        
        # Get top keywords by frequency
        sorted_words = sorted(word_counts.items(), key=lambda x: x[1], reverse=True)
        return [word for word, _ in sorted_words[:10]]  # Return top 10 keywords
    
    def process_file(self, file_path: Path, document_summary: str = "") -> List[Dict[str, Any]]:
        """
        Process a file into chunks with rich metadata.
        
        Args:
            file_path: Path to the document file
            document_summary: Optional summary for the whole document
            
        Returns:
            List of chunk dictionaries with metadata
        """
        # Extract text from file
        text = self.extract_text_from_file(file_path)
        if not text:
            return []
        
        # Split text into chunks
        chunks = self.text_splitter.split_text(text)
        print(f"Split '{file_path.name}' into {len(chunks)} chunks")
        
        # Process each chunk
        processed_chunks = []
        
        # If no document summary was provided, generate one
        if not document_summary:
            try:
                doc_summary_prompt = f"Provide a concise 8-word summary of this document title: {file_path.stem}"
                document_summary = self.llm.invoke(doc_summary_prompt).content.strip()
            except:
                document_summary = f"{file_path.stem} policy document"
        
        # First pass to create basic chunks
        basic_chunks = []
        for i, chunk_text in enumerate(chunks):
            chunk_id = f"{file_path.stem}_chunk_{i}"
            section_title = self.extract_section_title(chunk_text)
            
            chunk = {
                "id": chunk_id,
                "text": chunk_text,
                "chunk_id": chunk_id,
                "filename": file_path.name,
                "file_type": file_path.suffix.lstrip('.'),
                "file_path": str(file_path),
                "indexed_at": datetime.datetime.now().isoformat(),
                "section_title": section_title,
                "document_summary": document_summary,
                "semantic_keywords": self.extract_keywords(chunk_text)
            }
            basic_chunks.append(chunk)
        
        # Second pass to add related chunks and cross-chunk context
        for i, chunk in enumerate(basic_chunks):
            # Find related chunks (previous and next, if they exist)
            related_chunks = []
            if i > 0:
                related_chunks.append(basic_chunks[i-1]["chunk_id"])
            if i < len(basic_chunks) - 1:
                related_chunks.append(basic_chunks[i+1]["chunk_id"])
            
            chunk["related_chunks"] = related_chunks
            
            # Determine section context
            if i > 0 and basic_chunks[i-1]["section_title"] == chunk["section_title"]:
                chunk["section_context"] = f"Section: {chunk['section_title']} (continued)"
            else:
                chunk["section_context"] = f"Section: {chunk['section_title']}"
            
            # Generate chunk summary
            chunk["chunk_summary"] = self.generate_chunk_summary(chunk["text"])
            
            # Cross-references (simplified - in a real system you'd have a more sophisticated approach)
            # Here we're just adding dummy cross-references for demonstration
            chunk["cross_references"] = []
            
            processed_chunks.append(chunk)
        
        return processed_chunks
    
    def process_directory(self, directory_path: str) -> List[Dict[str, Any]]:
        """
        Process all supported documents in a directory.
        
        Args:
            directory_path: Path to directory containing documents
            
        Returns:
            List of chunk dictionaries with metadata
        """
        # Supported extensions
        supported_extensions = ['.pdf', '.docx', '.txt', '.md']
        
        # Get all files
        directory = Path(directory_path)
        all_files = [p for p in directory.glob('**/*') if p.is_file() and p.suffix.lower() in supported_extensions]
        
        print(f"Found {len(all_files)} supported documents to process in {directory_path}")
        
        all_chunks = []
        
        # Process each file
        for file_path in tqdm(all_files, desc="Processing files"):
            file_chunks = self.process_file(file_path)
            all_chunks.extend(file_chunks)
            print(f"Created {len(file_chunks)} chunks for {file_path.name}")
        
        print(f"Total document chunks created: {len(all_chunks)}")
        return all_chunks

# Now include the ZillizMigrationTool class
class ZillizMigrationTool:
    def __init__(self, voyage_api_key: str, zilliz_uri: str, zilliz_token: str, openai_api_key: str = None):
        """
        Initialize the migration tool with API keys and connection details.
        
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
            self.document_processor = DocumentProcessor(openai_api_key)
        print("Clients initialized successfully")
    
    def create_collection(self, collection_name: str, dimension: int = 1024):
        """
        Create a new collection in Zilliz Cloud with proper schema for all metadata.
        
        Args:
            collection_name: Name of the collection to create
            dimension: Dimension of the vectors to store (1024 for Voyage 3 Large)
        """
        if self.zilliz_client.has_collection(collection_name):
            print(f"Collection '{collection_name}' already exists. Dropping it.")
            self.zilliz_client.drop_collection(collection_name)
        
        from pymilvus import CollectionSchema, FieldSchema, DataType
        
        # Create proper schema with all your metadata fields
        fields = [
            FieldSchema(name="id", dtype=DataType.VARCHAR, max_length=100, is_primary=True),
            FieldSchema(name="text", dtype=DataType.VARCHAR, max_length=65535),
            FieldSchema(name="filename", dtype=DataType.VARCHAR, max_length=256),
            FieldSchema(name="file_type", dtype=DataType.VARCHAR, max_length=20),
            FieldSchema(name="file_path", dtype=DataType.VARCHAR, max_length=512),
            FieldSchema(name="indexed_at", dtype=DataType.VARCHAR, max_length=30),
            FieldSchema(name="chunk_id", dtype=DataType.VARCHAR, max_length=100),
            FieldSchema(name="section_title", dtype=DataType.VARCHAR, max_length=256),
            FieldSchema(name="chunk_summary", dtype=DataType.VARCHAR, max_length=512),
            FieldSchema(name="section_context", dtype=DataType.VARCHAR, max_length=256),
            FieldSchema(name="document_summary", dtype=DataType.VARCHAR, max_length=256),
            FieldSchema(name="related_chunks", dtype=DataType.JSON),
            FieldSchema(name="semantic_keywords", dtype=DataType.JSON),
            FieldSchema(name="cross_references", dtype=DataType.JSON),
            FieldSchema(name="vector", dtype=DataType.FLOAT_VECTOR, dim=dimension)
        ]
        
        schema = CollectionSchema(fields=fields, description="Document chunks with full metadata")
        
        # Create collection with proper schema
        self.zilliz_client.create_collection(
            collection_name=collection_name,
            schema=schema,
            consistency_level="Strong"
        )
        
        # Create vector index
        try:
            index_params = {
                "index_type": "HNSW",
                "metric_type": "COSINE", 
                "params": {"M": 16, "efConstruction": 200}
            }
            
            self.zilliz_client.create_index(
                collection_name=collection_name,
                field_name="vector",
                index_params=index_params
            )
            print("✅ Vector index created successfully")
        except Exception as e:
            print(f"⚠️ Could not create vector index: {e}")
        
        # Create text index for search (optional)
        try:
            text_index_params = {
                "index_type": "INVERTED"
            }
            
            self.zilliz_client.create_index(
                collection_name=collection_name,
                field_name="text",
                index_params=text_index_params
            )
            print("✅ Text index created successfully")
        except Exception as e:
            print(f"⚠️ Could not create text index: {e}")
    
        print(f"Collection '{collection_name}' created successfully with {len(fields)} fields and dimension {dimension}")
    
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
                # input_type "document" is recommended for indexing documents
                response = self.voyage_client.embed(
                    batch, 
                    model="voyage-3-large", 
                    input_type="document",
                    output_dimension=1024  # Explicitly set dimension for clarity
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
            self.create_collection(collection_name, EMBEDDING_DIM)
        
        # Insert chunks into collection
        self.insert_chunks(collection_name, chunks)
        
        return chunks
    
    def insert_chunks(self, collection_name: str, chunks: List[Dict[str, Any]], 
                 show_progress: bool = True):
        """
        Insert chunks with their enriched metadata and embeddings into Zilliz.
        
        Args:
            collection_name: Name of the collection to insert into
            chunks: List of chunk dictionaries with text and rich metadata
            show_progress: Whether to show a progress bar
        """
        # Extract text content for embedding
        texts = [chunk["text"] for chunk in chunks]
        
        # Generate embeddings
        embeddings = self.generate_embeddings(texts, show_progress)
        
        # Insert in batches
        batches = [(chunks[i:i + BATCH_SIZE], embeddings[i:i + BATCH_SIZE]) 
                for i in range(0, len(chunks), BATCH_SIZE)]
        
        if show_progress:
            batches = tqdm(batches, desc="Inserting chunks")
        
        for batch_chunks, batch_embeddings in batches:
            try:
                # Create insertion data using the proper schema field names
                insert_data = []
                for i, chunk in enumerate(batch_chunks):
                    # Use the exact field names from schema
                    chunk_data = {
                        "id": chunk["id"],
                        "text": chunk["text"],
                        "filename": chunk["filename"],
                        "file_type": chunk["file_type"],
                        "file_path": chunk["file_path"],
                        "indexed_at": chunk["indexed_at"],
                        "chunk_id": chunk["chunk_id"],
                        "section_title": chunk["section_title"],
                        "chunk_summary": chunk["chunk_summary"],
                        "section_context": chunk["section_context"],
                        "document_summary": chunk["document_summary"],
                        "related_chunks": chunk["related_chunks"],
                        "semantic_keywords": chunk["semantic_keywords"],
                        "cross_references": chunk["cross_references"],
                        "vector": batch_embeddings[i]  # Vector field
                    }
                    insert_data.append(chunk_data)
                
                # Insert the batch
                self.zilliz_client.insert(
                    collection_name=collection_name,
                    data=insert_data
                )
                
                # Avoid rate limiting
                if len(batches) > 1:
                    time.sleep(0.2)
                    
            except Exception as e:
                print(f"Error inserting batch: {e}")
        
        # Load the collection to make it available for search
        self.zilliz_client.load_collection(collection_name)
        print(f"Inserted {len(chunks)} chunks into collection '{collection_name}'")
    
    def search_chunks(self, collection_name: str, query: str, limit: int = 5, 
                 metadata_filter: Optional[str] = None) -> List[Dict[str, Any]]:
        """
        Search for chunks similar to the query text.
        
        Args:
            collection_name: Name of the collection to search in
            query: Query text
            limit: Maximum number of results to return
            metadata_filter: Optional filter expression for metadata
        
        Returns:
            List of chunk dictionaries with text, metadata, and score
        """
        try:
            # Generate embedding for the query
            response = self.voyage_client.embed(
                [query], 
                model="voyage-3-large", 
                input_type="query",
                output_dimension=1024
            )
            
            # Handle both object and dict response formats
            if hasattr(response, 'embeddings'):
                query_embedding = response.embeddings[0]
            elif isinstance(response, dict) and 'embeddings' in response:
                query_embedding = response['embeddings'][0]
            else:
                raise ValueError(f"Unexpected response format from Voyage AI: {type(response)}")
            
            # Define output fields to return - UPDATED for default field names
            output_fields = [
                "text", "chunk_summary", "section_title", "document_summary",
                "filename", "file_type", "section_context", "semantic_keywords",
                "related_chunks", "cross_references"
            ]
            
            # Perform the search - UPDATED for correct parameter structure
            search_params = [query_embedding]  # Just pass the embedding directly
            
            # Build search arguments
            search_args = {
                "collection_name": collection_name,
                "data": search_params,
                "anns_field": "vector",
                "limit": limit,
                "output_fields": output_fields
            }
            
            # Add metadata filter if provided
            if metadata_filter:
                search_args["filter"] = metadata_filter  # Use 'filter' not 'expr'
            
            search_results = self.zilliz_client.search(**search_args)
            
            # Format the results - UPDATED for new response format
            formatted_results = []
            if search_results and len(search_results) > 0:
                for hit in search_results[0]:
                    # CHANGE: Updated to handle the correct response structure
                    entity = hit.get("entity", hit)  # Handle different response formats
                    formatted_results.append({
                        "text": entity.get("text", ""),
                        "chunk_summary": entity.get("chunk_summary", ""),
                        "section_title": entity.get("section_title", ""),
                        "document_summary": entity.get("document_summary", ""),
                        "filename": entity.get("filename", ""),
                        "file_type": entity.get("file_type", ""),
                        "section_context": entity.get("section_context", ""),
                        "semantic_keywords": entity.get("semantic_keywords", []),
                        "related_chunks": entity.get("related_chunks", []),
                        "cross_references": entity.get("cross_references", []),
                        "score": hit.get("score", hit.get("distance", 0))  # Handle different score field names
                    })
            
            return formatted_results
            
        except Exception as e:
            print(f"Error searching documents: {e}")
            return []
    
    def hybrid_search_chunks(self, collection_name: str, query: str, limit: int = 5,
                            metadata_filter: Optional[str] = None) -> List[Dict[str, Any]]:
        """
        Perform a hybrid search combining semantic and keyword matching.
        
        Args:
            collection_name: Name of the collection to search in
            query: Query text
            limit: Maximum number of results to return
            metadata_filter: Optional filter expression for metadata
        
        Returns:
            List of document dictionaries with content, metadata, and score
        """
        # Extract potential keywords from the query
        keywords = [word for word in query.split() if len(word) > 3]
        
        # Create text match filter for keyword search
        text_match_filters = []
        for keyword in keywords:
            text_match_filters.append(f'TEXT_MATCH(text, "{keyword}")')
        
        # Combine with metadata filter if provided
        combined_filter = " OR ".join(text_match_filters)
        if metadata_filter:
            if combined_filter:
                combined_filter = f"({combined_filter}) AND ({metadata_filter})"
            else:
                combined_filter = metadata_filter
        
        try:
            # First attempt with combined filtering
            if combined_filter:
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
            
            # Fallback to standard semantic search
            print("No results with hybrid search, falling back to semantic search")
            return self.search_chunks(
                collection_name=collection_name,
                query=query,
                limit=limit,
                metadata_filter=metadata_filter
            )
            
        except Exception as e:
            print(f"Error in hybrid search: {e}")
            # Final fallback to basic search without filtering
            return self.search_chunks(
                collection_name=collection_name,
                query=query,
                limit=limit
            )

# Example usage
def main():
    # Initialize the migration tool with both Voyage and OpenAI API keys
    migration_tool = ZillizMigrationTool(
        voyage_api_key=VOYAGE_API_KEY,
        zilliz_uri=ZILLIZ_CLOUD_URI,
        zilliz_token=ZILLIZ_CLOUD_TOKEN,
        openai_api_key=OPENAI_API_KEY
    )
    
    # Process all documents in the directory and insert into Zilliz
    try:
        chunks = migration_tool.process_directory_and_insert(
            collection_name=COLLECTION_NAME,
            directory_path=DOCS_DIRECTORY
        )
        print(f"Successfully processed and inserted {len(chunks)} chunks")
        
        # Example searches using the new collection
        if chunks:
            print("\nSemantic Search Example:")
            results = migration_tool.search_chunks(
                collection_name=COLLECTION_NAME,
                query="What are the maternity leave entitlements?",
                limit=3
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
                limit=3,
                metadata_filter="file_type == \"pdf\""
            )
            for i, result in enumerate(results):
                print(f"Result {i+1}: {result['chunk_summary']}")
                print(f"Section: {result['section_title']}")
                print(f"From: {result['filename']} ({result['file_type']})")
                print(f"Score: {result['score']:.4f}")
                print("---")
            
            print("\nHybrid Search Example:")
            results = migration_tool.hybrid_search_chunks(
                collection_name=COLLECTION_NAME,
                query="maternity leave duration weeks",
                limit=3
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