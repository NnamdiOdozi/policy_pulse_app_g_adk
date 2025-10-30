"""
File Watcher for Automatic Document Ingestion to Zilliz

Monitors a directory for file changes and automatically:
- Processes new/modified files into chunks and indexes them in Zilliz
- Removes chunks when files are deleted
- Handles file renames by deleting old chunks and reprocessing

Usage:
    python file_watcher_zilliz.py

To stop: Press Ctrl+C
"""

import os
import time
from pathlib import Path
from datetime import datetime
from watchdog.observers import Observer
from watchdog.events import FileSystemEventHandler, FileMovedEvent
from dotenv import load_dotenv

# Import your existing Zilliz classes
from zilliz_embedding import ZillizMigrationTool

# Load environment variables
load_dotenv()

# Configuration - matches your existing setup
WATCH_DIRECTORY = "Policy Pulse + AVE collab"
COLLECTION_NAME = "WAE_docs_voyage_3_large"
DEBOUNCE_SECONDS = 2  # Wait 2 seconds after last event before processing
SUPPORTED_EXTENSIONS = {'.pdf', '.docx', '.pptx', '.odp', '.txt', '.md'}

# Initialize Zilliz client (reuses your existing setup)
zilliz_client = ZillizMigrationTool(
    voyage_api_key=os.getenv("VOYAGE_API_KEY"),
    zilliz_uri=os.getenv("ZILLIZ_CLOUD_URI"),
    zilliz_token=os.getenv("ZILLIZ_API_KEY"),
    openai_api_key=os.getenv("OPENAI_API_KEY")
)

class DocumentEventHandler(FileSystemEventHandler):
    """Handles file system events and manages debouncing."""
    
    def __init__(self):
        super().__init__()
        self.pending_events = {}  # filepath -> (event_type, timestamp)
        self.recent_renames = {}  # filepath -> timestamp (to ignore spurious modify events)

    def _should_process_file(self, file_path):
        """Check if file should be processed based on extension."""
        return Path(file_path).suffix.lower() in SUPPORTED_EXTENSIONS
    
    def _schedule_processing(self, file_path, event_type):
        """Schedule file for processing after debounce period."""
        if not self._should_process_file(file_path):
            return
            
        self.pending_events[file_path] = (event_type, time.time())
        print(f"[SCHEDULED] {event_type}: {file_path}")
    
    def on_created(self, event):
        """Handle file creation events."""
        if not event.is_directory:
            self._schedule_processing(event.src_path, "created")
    
    def on_modified(self, event):
        """Handle file modification events."""
        if not event.is_directory:
            # Check if this is a spurious modify event right after a rename
            if event.src_path in self.recent_renames:
                time_since_rename = time.time() - self.recent_renames[event.src_path]
                if time_since_rename < 1.0:  # Within 1 second of rename
                    print(f"[IGNORED] Spurious modify event after rename: {event.src_path}")
                    return
            
            self._schedule_processing(event.src_path, "modified")
    
    def on_deleted(self, event):
        """Handle file deletion events."""
        if not event.is_directory:
            self._schedule_processing(event.src_path, "deleted")
    
    def on_moved(self, event):
        """
        Handle file rename/move events with smart hash-based detection.
        
        Strategy:
        1. Calculate hash of "new" file
        2. Get stored hash from Zilliz for old path
        3. Compare hashes:
           - Same hash → Just update metadata (cheap)
           - Different hash → Delete old + process new (full reprocess)
        """
        if not event.is_directory:
            old_path = event.src_path
            new_path = event.dest_path
            
            # Only process if new path is a supported file type
            if not self._should_process_file(new_path):
                return
            
            # Track this rename to ignore spurious modify events
            self.recent_renames[new_path] = time.time()
            
            # Schedule a special "rename" event with old path info
            self.pending_events[new_path] = ("renamed", time.time(), old_path)
            
            print(f"[RENAME DETECTED] {Path(old_path).name} → {Path(new_path).name}")
    
    def process_pending_events(self):
        """
        Process events that have been pending longer than debounce period.
        Returns number of events processed.
        """
        current_time = time.time()

        # Clean up old rename tracking (older than 5 seconds)
        old_renames = [path for path, timestamp in self.recent_renames.items() 
                    if current_time - timestamp > 5.0]
        for path in old_renames:
            del self.recent_renames[path]

        events_to_process = []
        
        # Find events that have been quiet for DEBOUNCE_SECONDS
        for file_path, event_data in list(self.pending_events.items()):
            # Handle both formats: (event_type, timestamp) or (event_type, timestamp, old_path)
            if len(event_data) == 2:
                event_type, timestamp = event_data
                old_path = None
            else:
                event_type, timestamp, old_path = event_data
            
            if current_time - timestamp >= DEBOUNCE_SECONDS:
                events_to_process.append((file_path, event_type, old_path))
                del self.pending_events[file_path]
        
        # Process each event
        for file_path, event_type, old_path in events_to_process:
            try:
                if event_type in ("created", "modified"):
                    process_file_update(file_path)
                elif event_type == "deleted":
                    process_file_deletion(file_path)
                elif event_type == "renamed":
                    process_file_rename(file_path, old_path)
            except Exception as e:
                print(f"[ERROR] Failed to process {file_path}: {e}")
        
        return len(events_to_process)


def process_file_update(file_path):
    """
    Process a created or modified file with hash-based change detection:
    1. Calculate current file hash
    2. Query Zilliz for stored hash (from any chunk of this file)
    3. Compare hashes:
       - Same hash → Skip processing (no content change)
       - Different hash → Full reprocess
    """
    print(f"\n{'='*60}")
    print(f"[CHECKING] {file_path}")
    print(f"Time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    
    try:
        file_path_obj = Path(file_path)
        
        # Calculate current file hash
        current_hash = zilliz_client.document_processor.calculate_file_hash(file_path_obj)
        
        print(f"[INFO] Current hash: {current_hash[:16]}...")
        
        # Get stored hash from Zilliz (query any chunk from this file)
        stored_hash = zilliz_client.get_file_hash(COLLECTION_NAME, str(file_path_obj))
        
        if stored_hash:
            print(f"[INFO] Stored hash: {stored_hash[:16]}...")
            
            # Compare hashes
            if current_hash == stored_hash:
                print(f"[SKIPPED] No content changes detected (hash match)")
                print(f"{'='*60}\n")
                return
            else:
                print(f"[CONTENT CHANGED] Hash mismatch - reprocessing file")
        else:
            print(f"[NEW FILE] No existing hash found - processing file")
        
        # Process file (content changed or new file)
        chunks = zilliz_client.document_processor.process_file(file_path_obj)
        
        if not chunks:
            print(f"[WARNING] No chunks generated for {file_path}")
            return
        
        print(f"[INFO] Generated {len(chunks)} chunks")
        
        # Insert/update chunks in Zilliz
        zilliz_client.insert_chunks(
            collection_name=COLLECTION_NAME,
            chunks=chunks,
            show_progress=False
        )
        
        print(f"[SUCCESS] Indexed {len(chunks)} chunks to Zilliz")
        print(f"[SUCCESS] Hash saved: {current_hash[:16]}...")
        
    except Exception as e:
        print(f"[ERROR] Failed to process {file_path}: {e}")
        raise
    finally:
        print(f"{'='*60}\n")


def process_file_deletion(file_path):
    """
    Remove all chunks for a deleted file from Zilliz.
    """
    print(f"\n{'='*60}")
    print(f"[DELETING] Removing chunks for {file_path}")
    print(f"Time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    
    try:
        # Escape backslashes for Windows paths
        escaped_path = file_path.replace("\\", "\\\\")
        
        # Query to find all chunks for this file
        filter_expr = f'file_path == "{escaped_path}"'
        
        # Find all chunks for this file
        results = zilliz_client.zilliz_client.query(
            collection_name=COLLECTION_NAME,
            filter=filter_expr,
            output_fields=["id"],
            limit=10000
        )
        
        if not results:
            print(f"[INFO] No chunks found for {file_path}")
            print(f"{'='*60}\n")
            return
        
        # Extract chunk IDs
        chunk_ids = [result["id"] for result in results]
        print(f"[INFO] Found {len(chunk_ids)} chunks to delete")
        
        # Delete chunks by ID
        id_list = ", ".join([f'"{id}"' for id in chunk_ids])
        delete_expr = f'id in [{id_list}]'
        
        zilliz_client.zilliz_client.delete(
            collection_name=COLLECTION_NAME,
            filter=delete_expr
        )
        
        print(f"[SUCCESS] Deleted {len(chunk_ids)} chunks from Zilliz")
        
    except Exception as e:
        print(f"[ERROR] Failed to delete chunks for {file_path}: {e}")
    finally:
        print(f"{'='*60}\n")

def process_file_rename(new_path, old_path):
    """
    Handle file rename with hash-based smart detection.
    
    Strategy:
    1. Calculate hash of new file
    2. Get stored hash from Zilliz for old path
    3. Compare hashes:
       - Same → Update metadata only (no reprocessing)
       - Different → Full reprocess
    """
    print(f"\n{'='*60}")
    print(f"[RENAME] {old_path} → {new_path}")
    print(f"Time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    
    try:
        new_path_obj = Path(new_path)
        old_path_str = str(old_path)
        new_filename = new_path_obj.name
        new_path_str = str(new_path_obj)
        
        # Calculate hash of "new" file (same physical file, possibly moved/renamed)
        current_hash = zilliz_client.document_processor.calculate_file_hash(new_path_obj)
        
        print(f"[INFO] Current hash: {current_hash[:16]}...")
        
        # Get stored hash from old path
        stored_hash = zilliz_client.get_file_hash(COLLECTION_NAME, old_path_str)
        
        if stored_hash:
            print(f"[INFO] Stored hash: {stored_hash[:16]}...")
            
            if current_hash == stored_hash:
                # Content unchanged - just update metadata
                print(f"[METADATA ONLY] Content unchanged, updating metadata only")
                
                # Update all chunks' filename and file_path fields
                zilliz_client.update_chunks_metadata(
                    collection_name=COLLECTION_NAME,
                    old_file_path=old_path_str,
                    new_filename=new_filename,
                    new_file_path=new_path_str
                )
                
                print(f"[SUCCESS] Updated metadata without reprocessing")
            else:
                # Content changed during rename - full reprocess
                print(f"[FULL REPROCESS] Content changed during rename")
                
                # Delete old chunks
                process_file_deletion(old_path_str)
                
                # Process as new file
                process_file_update(new_path_str)
        else:
            # No old chunks found - treat as new file
            print(f"[NEW FILE] No existing chunks found, processing as new")
            process_file_update(new_path_str)
            
    except Exception as e:
        print(f"[ERROR] Failed to process rename: {e}")
    finally:
        print(f"{'='*60}\n")

def main():
    """Main file watching loop."""
    print("="*70)
    print("ZILLIZ DOCUMENT INGESTION FILE WATCHER")
    print("="*70)
    print(f"Watching directory: {WATCH_DIRECTORY}")
    print(f"Collection: {COLLECTION_NAME}")
    print(f"Debounce period: {DEBOUNCE_SECONDS} seconds")
    print(f"Supported extensions: {', '.join(SUPPORTED_EXTENSIONS)}")
    print("\nPress Ctrl+C to stop\n")
    print("="*70)
    print(f"voyage_api_key={os.getenv('VOYAGE_API_KEY')}")
    
    # Verify directory exists
    watch_path = Path(WATCH_DIRECTORY)
    if not watch_path.exists():
        print(f"[ERROR] Directory not found: {WATCH_DIRECTORY}")
        return
    
    # Initialize event handler and observer
    event_handler = DocumentEventHandler()
    observer = Observer()
    observer.schedule(event_handler, path=str(watch_path), recursive=True)
    observer.start()
    
    print(f"[STARTED] Watching for file changes...\n")
    
    try:
        while True:
            # Check for pending events every second
            time.sleep(1)
            event_handler.process_pending_events()
            
    except KeyboardInterrupt:
        print("\n[STOPPING] Shutting down file watcher...")
        observer.stop()
        observer.join()
        print("[STOPPED] File watcher terminated")


if __name__ == "__main__":
    # Verify required environment variables
    required_vars = ["VOYAGE_API_KEY", "ZILLIZ_CLOUD_URI", "ZILLIZ_API_KEY", "OPENAI_API_KEY"]
    missing_vars = [var for var in required_vars if not os.getenv(var)]
    
    if missing_vars:
        print(f"[ERROR] Missing required environment variables: {', '.join(missing_vars)}")
        print("Please set these in your .env file")
        exit(1)
    
    main()