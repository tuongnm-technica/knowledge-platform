from typing import List, Dict, Any

class ContextBuilder:
    @staticmethod
    def build(hits: List[Dict[str, Any]], max_tokens_per_group=2000, min_score=0.3) -> List[Dict[str, Any]]:
        """
        Nhóm các chunks (hits) theo document_id VÀ section_title để lọc noise (1 doc có thể nhiều topics).
        Có áp dụng Threshold điểm từ score và Token budget để không làm "nổ" token của LLM.
        """
        grouped = {}
        
        for hit in hits:
            score = hit.get("score", 0.0)
            
            # 1. Relevance Filtering (Drop chunk low score)
            if score < min_score:
                continue
                
            doc_id = hit["document_id"]
            sec_title = hit.get("section_title") or "General"
            
            # 2. Group by Topic / Section (thay vì chỉ Document_ID)
            group_key = f"{doc_id}_{sec_title}"
            
            if group_key not in grouped:
                grouped[group_key] = {
                    "document_id": doc_id,
                    "section_title": sec_title,
                    "title": hit.get("title", "Unknown"),
                    "source": hit.get("source", "unknown"),
                    "url": hit.get("url", ""),
                    "score": score, # Initialize with first score
                    "contents": [],
                    "assets": [],
                    "current_length_chars": 0
                }
            
            # Lấy max score đại diện cho cụm
            grouped[group_key]["score"] = max(grouped[group_key]["score"], score)
            
            # 3. Deduplicate
            content = hit.get("content", "").strip()
            if not content or content in grouped[group_key]["contents"]:
                continue
                
            # 4. Token budget control (1 token ~ 4 chars approximation)
            estimated_chars = len(content)
            max_chars_allowed = max_tokens_per_group * 4
            
            if grouped[group_key]["current_length_chars"] + estimated_chars > max_chars_allowed:
                # Nếu tràn, cắt gọt phần còn lại có thể nhét vừa
                rem_chars = max_chars_allowed - grouped[group_key]["current_length_chars"]
                if rem_chars > 200:
                    grouped[group_key]["contents"].append(content[:rem_chars] + "...[TRUNCATED BY BUDGET]")
                    grouped[group_key]["current_length_chars"] += rem_chars
                continue # Bỏ qua chunk này do đã hết budget của group này
                
            grouped[group_key]["contents"].append(content)
            grouped[group_key]["current_length_chars"] += estimated_chars
                
            # Gộp assets
            assets = hit.get("assets", [])
            for asset in assets:
                if asset not in grouped[group_key]["assets"]:
                    grouped[group_key]["assets"].append(asset)
                    
        # Hợp nhất các contents con -> đoạn văn tổng
        final_groups = []
        for group in grouped.values():
            merged_content = "\n\n... [Cùng thuộc Section: {}] ...\n\n".join(group["contents"]).format(group["section_title"])
            group["content"] = merged_content
            del group["contents"]
            del group["current_length_chars"]
            final_groups.append(group)
            
        # Sắp xếp theo thứ tự điểm Relevance lớn nhất
        final_groups.sort(key=lambda x: x["score"], reverse=True)
        return final_groups
