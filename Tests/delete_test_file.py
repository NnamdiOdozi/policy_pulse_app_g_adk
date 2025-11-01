import os
from dotenv import load_dotenv

# === PATH SETUP ===
# UNUSUAL: We manipulate sys.path to allow imports from parent directories
current_dir = os.path.dirname(os.path.abspath(__file__))
project_root = os.path.join(current_dir, '..') 
sys.path.insert(0, os.path.abspath(project_root))


from Zilliz_src.indexer import ZillizMigrationTool

load_dotenv()

client = ZillizMigrationTool(
    voyage_api_key=os.getenv("VOYAGE_API_KEY"),
    zilliz_uri=os.getenv("ZILLIZ_CLOUD_URI"),
    zilliz_token=os.getenv("ZILLIZ_API_KEY"),
    openai_api_key=os.getenv("OPENAI_API_KEY")
)

COLLECTION_NAME = "WAE_docs_voyage_3_large"

# The filename to delete (adjust if needed)
filename = "Module 1 Lesson 3 Compliance legal and ethical considerations.docx"

print(f"Searching for chunks with filename: {filename}")
print("="*60)

# First, let's see what we're about to delete
results = client.zilliz_client.query(
    collection_name=COLLECTION_NAME,
    filter=f'filename == "{filename}"',
    output_fields=["id", "chunk_id", "file_path"],
    limit=100
)

if not results:
    print("No chunks found for this filename!")
    exit()

print(f"Found {len(results)} chunks to delete:\n")

for i, chunk in enumerate(results[:5]):  # Show first 5
    print(f"{i+1}. ID: {chunk['id']}")
    print(f"   chunk_id: {chunk.get('chunk_id', 'N/A')}")
    print(f"   file_path: {chunk.get('file_path', 'N/A')}")
    print()

if len(results) > 5:
    print(f"... and {len(results) - 5} more chunks\n")

print("="*60)
print(f"\nThis will DELETE {len(results)} chunks from Zilliz.")
print("This action cannot be undone!")
print("\nAre you sure you want to proceed? Type 'DELETE' to confirm: ", end="")

confirmation = input().strip()

if confirmation == "DELETE":
    print("\nDeleting chunks...")
    
    # Extract all IDs
    chunk_ids = [chunk["id"] for chunk in results]
    
    # Delete in batches of 100
    batch_size = 100
    for i in range(0, len(chunk_ids), batch_size):
        batch = chunk_ids[i:i+batch_size]
        id_list = ", ".join([f'"{id}"' for id in batch])
        delete_expr = f'id in [{id_list}]'
        
        try:
            client.zilliz_client.delete(
                collection_name=COLLECTION_NAME,
                filter=delete_expr
            )
            print(f"  Deleted batch {i//batch_size + 1} ({len(batch)} chunks)")
        except Exception as e:
            print(f"  Error deleting batch: {e}")
    
    print(f"\n✅ Successfully deleted {len(chunk_ids)} chunks")
    print("\nVerifying deletion...")
    
    # Verify
    verify_results = client.zilliz_client.query(
        collection_name=COLLECTION_NAME,
        filter=f'filename == "{filename}"',
        output_fields=["id"],
        limit=10
    )
    
    if verify_results:
        print(f"⚠️  Warning: Still found {len(verify_results)} chunks after deletion")
        print("   (These might be soft-deleted and will disappear after compaction)")
    else:
        print("✅ Verification complete - no chunks remain")
else:
    print("\nCancelled. No chunks were deleted.")