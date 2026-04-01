import asyncio
import uuid
from services.llm_service import LLMService

async def test():
    print("Testing LLMService initialization with legacy 'model' argument...")
    try:
        llm = LLMService(model="test-model")
        print("SUCCESS: Initialization worked.")
    except TypeError as e:
        print(f"FAILED: Initialization error: {e}")
    
    print("\nTesting is_available()...")
    try:
        # This might fail if no provider is configured in the environment, but it shouldn't throw AttributeError
        avail = await llm.is_available()
        print(f"Result: {avail}")
    except AttributeError as e:
        print(f"FAILED: Method missing: {e}")
    except Exception as e:
        print(f"Caught expected or other error: {e}")

if __name__ == "__main__":
    asyncio.run(test())
