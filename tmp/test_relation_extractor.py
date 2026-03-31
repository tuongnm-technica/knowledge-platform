import asyncio
from graph.relation_extractor import SemanticRelationExtractor

async def main():
    extractor = SemanticRelationExtractor()
    text = """
    Hệ thống Thanh toán (Payment Service) phụ thuộc vào Service Users để lấy thông tin. 
    Khi thanh toán thành công, nó kích hoạt luồng Gửi Email. 
    Frontend Web Application thì gọi tới Payment Service này để lấy mã QR.
    """
    print(f"Testing text:\n{text}\n")
    print("Calling LLM extractor...")
    
    relations = await extractor.extract(text)
    
    print("\n[RESULT]")
    for r in relations:
        print(f" - [{r.get('subject')}] --({r.get('predicate')})--> [{r.get('object')}]")

if __name__ == "__main__":
    asyncio.run(main())
