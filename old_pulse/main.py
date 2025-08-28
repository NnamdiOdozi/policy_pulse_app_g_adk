# %%
import os
#import pinecone
#from pinecone import Pinecone
from dotenv import load_dotenv
from pathlib import Path
from collections import Counter
#from tqdm.notebook import tqdm
from langchain.text_splitter import RecursiveCharacterTextSplitter
#from langchain_pinecone import PineconeVectorStore
import json
from embeddings_utils import process_directory, upload_to_pinecone
from ai_agent import interactive_qa

# %%
# Load variables from .env into environment
load_dotenv()

# Access them
PINECONE_API_KEY = os.getenv("PINECONE_API_KEY")
OPEN_API_API_KEY = os.getenv("OPENAI_API_KEY")
HF_TOKEN = os.getenv("HF_TOKEN")
SONAR_API_KEY = os.getenv("SONAR_API_KEY")

# %%
# Directory to search
directory = Path("Policy Pulse + AVE collab")

# Patterns for PDFs, Word, and PowerPoint documents
file_extensions = ["**/*.pdf"]#, "**/*.docx", "**/*.pptx"]

# Collect all matching files recursively for the specified extensions
#file_paths = [str(p) for ext in file_extensions for p in directory.glob(ext)]
file_paths = [str(p) for p in directory.glob('**/*')]

# Print the list of files
file_paths


# %%
print(f"the number of actual files is:{len([str(p) for p in directory.glob('**/*') if p.is_file()])}")
print(f"the number of actual folders is:{len([str(p) for p in directory.glob('**/*') if p.is_dir()])}")

# %%

# Directory to search
directory = Path("Policy Pulse + AVE collab")

# Get all files (excluding directories)
all_files = [p for p in directory.glob('**/*') if p.is_file()]

# Count by extension
extension_counts = Counter([p.suffix.lower() for p in all_files])

# Print counts by extension
for ext, count in extension_counts.most_common():
    print(f"{ext or '(no extension)'}: {count} files")

# Print total
print(f"\nTotal number of files: {len(all_files)}")

# %% [markdown]
# 

# %% [markdown]
# ![image.png](attachment:image.png)

# %%
# Initialize the text splitter
text_splitter = RecursiveCharacterTextSplitter(
    chunk_size=2000,
    chunk_overlap=400,
    length_function=len,
)



# %%
import importlib
import embeddings_utils
importlib.reload(embeddings_utils)

# Re-import the functions if needed
from embeddings_utils import process_directory, upload_to_pinecone

# %%
# Directory containing your documents
directory_path = "Policy Pulse + AVE collab"
index_name = "policypulse"  # Replace with your Pinecone index name

# Process all documents
documents = process_directory(directory_path, text_splitter)

#  Save documents metadata locally
print("Saving document metadata...")
with open("documents_metadata.json", "w") as f:
    # Save just the metadata and IDs for reference
    metadata_records = [{"id": doc["id"], "metadata": doc["metadata"]} for doc in documents]
    json.dump(metadata_records, f, indent=2)


# Upload to Pinecone
pinecone_api_key = PINECONE_API_KEY  # Replace with your Pinecone API key
index_name = "policypulse"  # Your index name

# Uncomment to upload
upload_to_pinecone(documents, index_name, pinecone_api_key)

print("Process completed!")

# %%
# When saving metadata and text chunks for viewing:
with open("documents_metadata_and_chunks.json", "w", encoding="utf-8") as f:
    # Convert each document to a dict with formatted metadata and full text
    viewable_docs = []
    for doc in documents:
        # Create a copy with formatted text for better viewing
        doc_copy = {
            "id": doc["id"],
            "metadata": doc["metadata"],
            # Format the text to be more readable in the JSON file
            "text_sample": doc["text"][:500] + "..." if len(doc["text"]) > 500 else doc["text"]
        }
        viewable_docs.append(doc_copy)
    
    # Use indent for formatting and ensure_ascii=False for proper character handling
    json.dump(viewable_docs, f, indent=2, ensure_ascii=False)

# %%
# For a more readable output of chunks:
with open("document_chunks.txt", "w", encoding="utf-8") as f:
    for i, doc in enumerate(documents):
        f.write(f"\n{'='*80}\n")
        f.write(f"CHUNK {i+1}: {doc['id']}\n")
        f.write(f"{'='*80}\n\n")
        f.write(doc["text"])
        f.write("\n\n")

# %%
interactive_qa("policypulse", SONAR_API_KEY)

# %%


# %%



