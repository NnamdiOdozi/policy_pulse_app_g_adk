# Create reprocess_test_file.py
import os
from pathlib import Path
from dotenv import load_dotenv
from zilliz_embedding import ZillizMigrationTool

load_dotenv()

client = ZillizMigrationTool(
    voyage_api_key=os.getenv("VOYAGE_API_KEY"),
    zilliz_uri=os.getenv("ZILLIZ_CLOUD_URI"),
    zilliz_token=os.getenv("ZILLIZ_API_KEY"),
    openai_api_key=os.getenv("OPENAI_API_KEY")
)

COLLECTION_NAME = "WAE_docs_voyage_3_large"

# Path to the test file
file_path = Path("Policy Pulse + AVE collab/Module 1/Module 1 Lesson 3 Compliance legal and ethical considerations.docx")

print(f"Processing file: {file_path.name}")

# Process the file
chunks, file_hash, file_size = client.process_single_file_and_insert(
    collection_name=COLLECTION_NAME,
    file_path=file_path
)

print(f"\n✅ Successfully processed:")
print(f"   Chunks created: {len(chunks)}")
print(f"   File hash: {file_hash[:16]}...")
print(f"   File size: {file_size} bytes")