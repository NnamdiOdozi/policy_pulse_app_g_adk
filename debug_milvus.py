#!/usr/bin/env python3
"""
Debug script to test create_collection behavior
This will help identify where exactly the error occurs in collection creation.
"""

import os
from pymilvus import MilvusClient, DataType

# Configuration - use your same values
ZILLIZ_CLOUD_URI = os.environ.get("ZILLIZ_CLOUD_URI", "https://in03-768dd5416cd6745.serverless.aws-eu-central-1.cloud.zilliz.com")
ZILLIZ_CLOUD_TOKEN = os.environ.get("ZILLIZ_API_KEY", "your-zilliz-token-here")
COLLECTION_NAME = "debug_test_collection"
EMBEDDING_DIM = 1024

def debug_create_collection():
    """Debug the create_collection method step by step."""
    print("=== DEBUGGING create_collection() BEHAVIOR ===")
    
    # Initialize client
    try:
        client = MilvusClient(
            uri=ZILLIZ_CLOUD_URI,
            token=ZILLIZ_CLOUD_TOKEN
        )
        print("✅ Client initialized successfully")
    except Exception as e:
        print(f"❌ Client initialization failed: {e}")
        return

    # Clean up - drop collection if it exists
    try:
        if client.has_collection(COLLECTION_NAME):
            print(f"🧹 Dropping existing collection '{COLLECTION_NAME}'")
            client.drop_collection(COLLECTION_NAME)
            print("✅ Collection dropped")
    except Exception as e:
        print(f"⚠️ Warning: Could not drop collection: {e}")

    # Test 1: Simple create_collection (your current approach)
    print(f"\n🔍 TEST 1: Simple create_collection with schema parameter")
    try:
        # This is the exact approach from your code
        schema = {
            "collection_name": COLLECTION_NAME,
            "fields": [
                {
                    "name": "id",
                    "type": DataType.VARCHAR,
                    "is_primary": True,
                    "max_length": 100
                },
                {
                    "name": "text",
                    "type": DataType.VARCHAR,
                    "max_length": 65535
                },
                {
                    "name": "embedding",
                    "type": DataType.FLOAT_VECTOR,
                    "dim": EMBEDDING_DIM
                }
            ]
        }
        
        print("📝 Schema created, calling create_collection...")
        
        result = client.create_collection(
            collection_name=COLLECTION_NAME,
            dimension=EMBEDDING_DIM,
            primary_field_name="id",
            id_type=DataType.VARCHAR,
            vector_field_name="embedding",
            auto_id=False,
            metric_type="COSINE",
            schema=schema  # ← THIS MIGHT BE THE PROBLEM
        )
        
        print(f"✅ create_collection returned: {result}")
        print(f"Return type: {type(result)}")
        
    except Exception as e:
        print(f"❌ TEST 1 FAILED: {e}")
        print(f"❌ Error type: {type(e)}")
        import traceback
        traceback.print_exc()

    # Clean up for next test
    try:
        if client.has_collection(COLLECTION_NAME):
            client.drop_collection(COLLECTION_NAME)
    except:
        pass

    # Test 2: Simple create_collection (without schema)
    print(f"\n🔍 TEST 2: Simple create_collection without schema parameter")
    try:
        result = client.create_collection(
            collection_name=COLLECTION_NAME,
            dimension=EMBEDDING_DIM,
            primary_field_name="id",
            id_type=DataType.VARCHAR,
            vector_field_name="embedding",
            auto_id=False,
            metric_type="COSINE"
            # No schema parameter
        )
        
        print(f"✅ create_collection returned: {result}")
        print(f"Return type: {type(result)}")
        
    except Exception as e:
        print(f"❌ TEST 2 FAILED: {e}")
        print(f"❌ Error type: {type(e)}")
        import traceback
        traceback.print_exc()

    # Clean up for next test
    try:
        if client.has_collection(COLLECTION_NAME):
            client.drop_collection(COLLECTION_NAME)
    except:
        pass

    # Test 3: Quick setup approach
    print(f"\n🔍 TEST 3: Quick setup approach")
    try:
        result = client.create_collection(
            collection_name=COLLECTION_NAME,
            dimension=EMBEDDING_DIM
        )
        
        print(f"✅ create_collection returned: {result}")
        print(f"Return type: {type(result)}")
        
    except Exception as e:
        print(f"❌ TEST 3 FAILED: {e}")
        print(f"❌ Error type: {type(e)}")
        import traceback
        traceback.print_exc()

    # Clean up
    try:
        if client.has_collection(COLLECTION_NAME):
            client.drop_collection(COLLECTION_NAME)
            print("🧹 Test collection cleaned up")
    except:
        pass

if __name__ == "__main__":
    debug_create_collection()