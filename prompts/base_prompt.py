# Base context cho tất cả prompts — thông tin về công ty
COMPANY_CONTEXT = """Công ty: Technica
Hệ thống: Knowledge Platform (RAG on-premise)
Nguồn dữ liệu: Confluence, Jira, Slack, File Server nội bộ
Ngôn ngữ chính: Tiếng Việt"""

# Instruction chung tái sử dụng
BASE_RULES = """- Chỉ dùng thông tin từ tài liệu được cung cấp
- Trả lời bằng tiếng Việt
- Dẫn nguồn rõ ràng
- Không bịa đặt thông tin"""