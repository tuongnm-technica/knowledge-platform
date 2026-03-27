from __future__ import annotations
import json
from typing import TypedDict, Annotated, List, Optional, AsyncGenerator
from pydantic import BaseModel, Field
from langgraph.graph import StateGraph, START, END
from langchain_ollama import ChatOllama
from langchain_core.prompts import ChatPromptTemplate
from sqlalchemy.ext.asyncio import AsyncSession
import structlog
from config.settings import settings
from retrieval.hybrid.hybrid_search import HybridSearch
from graph.knowledge_graph import KnowledgeGraph
from persistence.document_repository import DocumentRepository
from permissions.filter import PermissionFilter

log = structlog.get_logger(__name__)

# ==========================================
# 1. DEFINING THE STATE
# ==========================================
# State này sẽ được truyền qua lại giữa các Agents.
# Chứa dữ liệu đầu vào và các JSON output của từng Agent.
class SDLCState(TypedDict):
    user_request: str
    context_documents: str  # Dữ liệu lấy từ RAG nếu cần
    ba_document_json: Optional[dict]
    sa_document_json: Optional[dict]
    qa_document_json: Optional[dict]
    current_status: str
    user_id: str  # Added to handle permission checks
    session: Optional[AsyncSession] # Added for DB access in nodes

# ==========================================
# 2. PYDANTIC SCHEMAS (LAYER 3)
# ==========================================
# Đại diện cho Layer 3 (JSON Schema) của GPT-4 Document Writer
class UseCase(BaseModel):
    id: str = Field(description="Mã UC, VD: UC-01")
    name: str
    actor: str
    trigger: str
    preconditions: List[str]
    main_flow: List[str]
    fe_technical_note: str

class BADocumentOutput(BaseModel):
    doc_id: str
    doc_type: str
    use_cases: List[UseCase]
    # Có thể thêm validation_rules, traceability_matrix theo đúng template của bạn

# Tương tự cho SA Document Output (Layer 3 của GPT-3 Solution Designer)
class SADocumentOutput(BaseModel):
    design_id: str
    review_ref: str
    architecture_overview: str
    api_contracts: List[dict]

# Schema cho QA Document Output (Layer 3 - Test Cases)
class TestCase(BaseModel):
    tc_id: str
    ac_ref: str
    type: str = Field(description="Positive, Negative, Boundary")
    preconditions: str
    steps: List[str]
    test_data: str
    expected_result: str

class QADocumentOutput(BaseModel):
    test_plan_id: str
    test_cases: List[TestCase]

# ==========================================
# 3. AGENT NODES
# ==========================================
# Khởi tạo model Local thông qua Ollama
llm = ChatOllama(
    base_url=settings.OLLAMA_BASE_URL,
    model=settings.OLLAMA_LLM_MODEL,
    temperature=0,
    num_ctx=16384,        # Mở rộng Context Window lên 16k token
    num_predict=8192,    # Tăng số lượng token output tối đa lên 8k
)

async def search_agent_node(state: SDLCState) -> dict:
    log.info("agent.search_agent.start", query=state["user_request"])
    session = state.get("session")
    if not session:
        log.warning("agent.search_agent.no_session")
        return {"current_status": "Search Skipped (No DB Session)"}

    # 1. Initialize Searchers
    searcher = HybridSearch(session)
    graph = KnowledgeGraph(session)
    permissions = PermissionFilter(session)
    repo = DocumentRepository(session)
    
    # 2. Extract Entities (Keyword focus: take Uppercase words or quoted terms)
    # Simple regex for capitalized words / specific project patterns
    entities = re.findall(r'[A-Z][A-Z0-9]+', state["user_request"])
    
    try:
        # 3. Permission Check
        allowed_ids = await permissions.allowed_docs(state["user_id"])
        
        # 4. Perform Hybrid Search
        results = await searcher.search(
            state["user_request"], 
            top_k=5, 
            allowed_document_ids=allowed_ids
        )
        
        # 5. Graph Supplement
        graph_ids = await graph.find_related_documents(entities, limit=5)
        if allowed_ids:
            graph_ids = [str(gid) for gid in graph_ids if str(gid) in {str(aid) for aid in allowed_ids}]
        
        # 6. Fetch Metadata & Content
        all_doc_ids = list({r["document_id"] for r in results} | set(graph_ids))
        docs = await repo.get_by_ids(all_doc_ids)
        
        context_str = "\n\n".join([
            f"--- Document: {d.get('title')} ---\n{d.get('content', '')[:6000]}"
            for d in docs
        ])
        
        log.info("agent.search_agent.done", found_docs=len(docs))
        return {
            "context_documents": context_str,
            "current_status": f"Found {len(docs)} relevant knowledge units."
        }
    except Exception as e:
        log.error("agent.search_agent.error", error=str(e))
        return {"current_status": "Search error, proceeding with limited context."}

import re # Needed for simple entity extraction

def ba_agent_node(state: SDLCState) -> dict:
    log.info("agent.ba_writer.start")
    
    # Cấu trúc LLM để ép trả về JSON theo đúng Pydantic Model (Layer 3)
    structured_llm = llm.with_structured_output(BADocumentOutput)
    
    # Layer 1: Prompt
    system_prompt = """You are Step 1: Requirement Analyst in the MyGPT BA Suite pipeline.
Your job: produce enterprise-grade BA documents in VIETNAMESE.
GOLDEN RULE: Every document must be complete enough that a developer can implement without asking questions.
Phân tích sâu, chi tiết từng Use Case, Validation Rule và Business Rule. 
TOÀN BỘ nội dung mô tả, ghi chú kỹ thuật phải được viết bằng TIẾNG VIỆT chuyên nghiệp, giàu thông tin.
Only output valid JSON matching the schema."""

    prompt = ChatPromptTemplate.from_messages([
        ("system", system_prompt),
        ("human", "Yêu cầu nghiệp vụ: {request}\n\nNgữ cảnh đính kèm: {context}")
    ])
    
    chain = prompt | structured_llm
    result = chain.invoke({
        "request": state["user_request"],
        "context": state.get("context_documents", "Không có")
    })
    
    log.info("agent.ba_writer.done", doc_id=result.doc_id)
    
    # Trả về các field cần update trong State
    return {
        "ba_document_json": result.model_dump(),
        "current_status": "BA Document Created"
    }

def sa_agent_node(state: SDLCState) -> dict:
    log.info("agent.sa_designer.start")
    ba_json = state.get("ba_document_json", {})
    
    structured_llm = llm.with_structured_output(SADocumentOutput)
    system_prompt = """You are Step 3: Solution Designer in the MyGPT BA Suite. 
Read the BA JSON Document (Use Cases, Validation rules) and produce a high-level technical design and API Contracts.
Thiết kế hệ thống chi tiết, bao hàm kiến trúc, data model và các API contract đầy đủ.
Mọi nội dung diễn giải, kiến trúc tổng quan phải được viết bằng TIẾNG VIỆT chuyên nghiệp."""
    
    prompt = ChatPromptTemplate.from_messages([
        ("system", system_prompt),
        ("human", "BA Document JSON:\n{ba_json}")
    ])
    
    chain = prompt | structured_llm
    result = chain.invoke({"ba_json": json.dumps(ba_json, ensure_ascii=False)})
    
    log.info("agent.sa_designer.done")
    return {
        "sa_document_json": result.model_dump(),
        "current_status": "SA Design Created"
    }

def qa_agent_node(state: SDLCState) -> dict:
    log.info("agent.qa_engineer.start")
    ba_json = state.get("ba_document_json", {})
    
    structured_llm = llm.with_structured_output(QADocumentOutput)
    # Sử dụng đúng mẫu QA-01 trong SDLC_Prompt_Library_v1.md của bạn
    system_prompt = """Bạn là QA Engineer có kinh nghiệm theo chuẩn ISTQB. 
Sinh test cases chi tiết từ các Use Cases và Validation Rules trong tài liệu BA.
Mỗi AC scenario -> >=3 test cases (1 positive + 1 negative + 1 boundary).
Mô tả các steps và expected result rõ ràng, chi tiết bằng TIẾNG VIỆT."""

    prompt = ChatPromptTemplate.from_messages([
        ("system", system_prompt),
        ("human", "BA Document JSON (Dùng Use Cases & Validation để viết Test Cases):\n{ba_json}")
    ])
    
    chain = prompt | structured_llm
    result = chain.invoke({"ba_json": json.dumps(ba_json, ensure_ascii=False)})
    
    log.info("agent.qa_engineer.done")
    return {
        "qa_document_json": result.model_dump(),
        "current_status": "QA Test Cases Created"
    }

# ==========================================
# 4. BUILD THE GRAPH ORCHESTRATOR
# ==========================================
workflow = StateGraph(SDLCState)

# Thêm các Agent vào Graph
workflow.add_node("search_agent", search_agent_node)
workflow.add_node("ba_agent", ba_agent_node)
workflow.add_node("sa_agent", sa_agent_node)
workflow.add_node("qa_agent", qa_agent_node)

# Định nghĩa luồng (Pipeline)
workflow.add_edge(START, "search_agent")   # Bắt đầu bằng việc tìm kiếm kiến thức
workflow.add_edge("search_agent", "ba_agent") # Sau đó mới chuyển thông tin cho BA
workflow.add_edge("ba_agent", "sa_agent")
workflow.add_edge("sa_agent", "qa_agent")
workflow.add_edge("qa_agent", END)

# Compile thành ứng dụng chạy được
sdlc_app = workflow.compile()

async def run_sdlc_pipeline(user_request: str, user_id: str, session: AsyncSession, context: str = "") -> dict:
    """Hàm helper để gọi từ FastAPI"""
    initial_state = {
        "user_request": user_request,
        "context_documents": context,
        "user_id": user_id,
        "session": session,
        "current_status": "Started"
    }
    # Chạy graph (luồng)
    final_state = await sdlc_app.ainvoke(initial_state)
    return final_state

async def stream_sdlc_pipeline(user_request: str, user_id: str, session: AsyncSession, context: str = "") -> AsyncGenerator[str, None]:
    """Hàm streaming phát sự kiện Server-Sent Events (SSE) cho Frontend"""
    initial_state = {
        "user_request": user_request,
        "context_documents": context,
        "user_id": user_id,
        "session": session,
        "current_status": "Started"
    }
    
    # astream_events giúp theo dõi tiến trình chạy của từng Node (Agent)
    async for event in sdlc_app.astream_events(initial_state, version="v1"):
        kind = event["event"]
        node_name = event.get("name", "")
        
        if kind == "on_chat_model_stream":
            # Stream token nếu muốn hiển thị text đang gõ (optional)
            pass 
        elif kind == "on_chain_start" and node_name in ["ba_agent", "sa_agent", "qa_agent"]:
            yield f"data: {json.dumps({'status': f'Agent {node_name} started...'})}\n\n"
        elif kind == "on_chain_end" and node_name in ["ba_agent", "sa_agent", "qa_agent"]:
            yield f"data: {json.dumps({'status': f'Agent {node_name} completed!', 'node': node_name})}\n\n"
            
    yield f"data: {json.dumps({'status': 'DONE'})}\n\n"