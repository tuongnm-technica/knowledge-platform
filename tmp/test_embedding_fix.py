import asyncio
import sys
import os

# Add project root to path
sys.path.append(os.getcwd())

from services.embedding_service import get_embedding_service

async def test_embedding():
    print("--- Testing Embedding Service Refactor ---")
    
    svc = get_embedding_service()
    
    test_text = "This is a test of the unified model management system."
    print(f"Testing single embedding for: '{test_text}'")
    
    try:
        # Note: this will use LLMService which resolves from DB or settings fallback.
        # It handles the semaphore too.
        vector = await svc.get_embedding(test_text, use_cache=False)
        if vector:
            print(f"Success! Vector length: {len(vector)}")
        else:
            print("Received empty vector.")
    except Exception as e:
        print(f"Failed single embedding: {str(e)}")

    test_batch = ["Hello world", "Artificial Intelligence is cool"]
    print(f"\nTesting batch embedding for: {test_batch}")
    try:
        vectors = await svc.get_embeddings_batch(test_batch, use_cache=False)
        print(f"Success! Batch size: {len(vectors)}")
        for i, v in enumerate(vectors):
            print(f"  Vector {i} length: {len(v)}")
    except Exception as e:
        print(f"Failed batch embedding: {str(e)}")

if __name__ == "__main__":
    asyncio.run(test_embedding())
