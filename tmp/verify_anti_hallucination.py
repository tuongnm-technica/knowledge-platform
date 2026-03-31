import asyncio
import structlog
from orchestration.agent import OllamaLLM
from orchestration.doc_orchestrator import DocOrchestrator
from prompts.doc_draft_prompt import build_doc_system_prompt, build_doc_user_prompt

# Mocking the logger
structlog.configure()

async def verify():
    from config.settings import settings
    # Patch for host execution (since host.docker.internal isn't reachable from Windows host normally)
    settings.OLLAMA_BASE_URL = "http://localhost:11434"
    
    llm = OllamaLLM()
    orchestrator = DocOrchestrator(llm)
    
    # Test 1: Requirements Intake with empty/vague input
    doc_type = "requirements_intake"
    system_prompt = build_doc_system_prompt(doc_type=doc_type)
    user_prompt = build_doc_user_prompt(
        doc_type=doc_type,
        question="Tạo yêu cầu cho một module mới không xác định.",
        answer="Không có thông tin bổ sung.",
        sources=[],
        documents=[]
    )
    
    print("--- STARTING VERIFICATION ---")
    print(f"Doc Type: {doc_type}")
    
    result = await orchestrator.generate_document_pipeline(
        system=system_prompt,
        user=user_prompt,
        max_tokens=2000
    )
    
    print("\n--- FINAL OUTPUT ---")
    print(result)
    
    # Check for hallucinations
    hallucinations = ["RAG Retrieval", "ATRS", "Source Priority", "BR-Version-History"]
    found = [h for h in hallucinations if h.lower() in result.lower()]
    
    if found:
        print(f"\n[FAILED] Found hallucinations: {found}")
    else:
        print("\n[SUCCESS] No common hallucinations found in the output.")

if __name__ == "__main__":
    asyncio.run(verify())
