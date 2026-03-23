"""
retrieval/context_compressor.py

Compress retrieved chunks before LLM summarization.
Tối ưu hóa: Sắp xếp theo score và lọc bỏ các đoạn rác có điểm thấp.
"""

import structlog

log = structlog.get_logger()

MAX_DOCS = 12
MAX_CHARS = 10000
# Ngưỡng điểm tối thiểu để coi là tài liệu có giá trị (sau khi Reranker chấm 3 điểm + rrf_score)
MIN_RELEVANCE_SCORE = 1.0 

def _score_value(source: dict) -> float:
    try:
        return float(
            source.get("rerank_score")
            or source.get("combined_score")
            or source.get("agent_score")
            or source.get("score")
            or 0
        )
    except Exception:
        return 0.0


def _as_text(value) -> str:
    if value is None:
        return ""
    if isinstance(value, str):
        return value
    try:
        return str(value)
    except Exception:
        return ""


def compress_context(sources, max_chars=MAX_CHARS):
    """    Nén và lọc context dựa trên điểm số từ Reranker.
    """
    if not sources:
        return ""
    # 1. Sắp xếp theo score giảm dần (Ưu tiên kết quả từ Reranker)
    sources = sorted(sources, key=_score_value, reverse=True)
    # 2. Lọc bỏ các kết quả có điểm quá thấp để tránh làm nhiễu LLM Summarizer
    # Nếu Reranker chấm 0 hoặc 1 điểm, score tổng thường sẽ thấp hơn 1.0
    valid_sources = [s for s in sources if _score_value(s) >= MIN_RELEVANCE_SCORE]
   
    # Fallback: Nếu không có kết quả nào đạt ngưỡng, lấy tạm 3 kết quả đầu tiên để tránh bị rỗng
    if not valid_sources:
        valid_sources = sources[:3]
    else:
        # Giới hạn số lượng tài liệu để context tập trung nhất có thể
        valid_sources = valid_sources[:MAX_DOCS]

    blocks = []
    total = 0
    
    for s in valid_sources:
        title   = s.get("title", "Untitled")
        source  = s.get("source", "Unknown")
        score   = _score_value(s)
        content = _as_text(s.get("content") or s.get("snippet") or "").strip()

        if not content:
            continue

        header = f"Title: {title}\nSource: {source}\nScore: {round(score, 3)}\nContent:\n"
        remaining = max_chars - total
        max_content_len = remaining - len(header)
        if max_content_len <= 0:
            break
        if len(content) > max_content_len:
            content = content[: max(0, max_content_len - 1)].rstrip() + "…"
        block = (header + content).strip()
        
        # Kiểm tra giới hạn ký tự (Context Window)
        if total + len(block) > max_chars:
            log.warn("context_compressor.truncated", current_total=total, next_block_len=len(block))
            break
            
        blocks.append(block)
        total += len(block)

    result_context = "\n\n---\n\n".join(blocks)
    
    log.info(
        "context.compressed.done", 
        input_count=len(sources), 
        output_count=len(blocks),
        total_chars=total
    )
    
    return result_context
