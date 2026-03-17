"""
Script nhập dữ liệu mẫu để test API
Chạy: python seed_data.py
"""

import asyncio
import uuid
from datetime import datetime
from sqlalchemy.ext.asyncio import AsyncSession
from storage.db.db import AsyncSessionLocal, create_tables
from ingestion.pipeline import IngestionPipeline
from models.document import Document, SourceType
from indexing.vector_index import VectorIndex
from indexing.keyword_index import KeywordIndex
from persistence.document_repository import DocumentRepository
from ingestion.cleaner import TextCleaner
from ingestion.chunker import TextChunker

try:
    import bcrypt
except ImportError:  # pragma: no cover - seed helper
    bcrypt = None


# ─── Data mẫu ─────────────────────────────────────────────────────────────────
SAMPLE_DOCUMENTS = [
    {
        "source": SourceType.CONFLUENCE,
        "source_id": "CONF-001",
        "title": "Hướng dẫn onboarding nhân viên mới",
        "content": """
        Chào mừng bạn đến với công ty! Đây là hướng dẫn onboarding cho nhân viên mới.
        
        Tuần 1: Làm quen với team và môi trường làm việc
        - Gặp gỡ HR để hoàn tất thủ tục giấy tờ
        - Nhận thiết bị làm việc: laptop, badge, tài khoản email
        - Tham gia buổi orientation về văn hóa công ty
        - Gặp gỡ manager và team members
        
        Tuần 2: Làm quen với hệ thống và công cụ
        - Cài đặt các công cụ cần thiết: Slack, Jira, Confluence
        - Tham gia các kênh Slack quan trọng: #general, #engineering, #announcements
        - Đọc tài liệu kỹ thuật của team
        - Shadow một senior engineer trong 3 ngày đầu
        
        Tuần 3-4: Bắt đầu làm việc thực tế
        - Nhận task đầu tiên từ Jira
        - Tham gia daily standup mỗi sáng 9h
        - Code review với team
        - Hoàn thành module đầu tiên
        
        Liên hệ HR: hr@company.com nếu có thắc mắc.
        """,
        "url": "https://confluence.company.com/onboarding",
        "author": "HR Team",
        "permissions": ["group_all_employees"],
    },
    {
        "source": SourceType.CONFLUENCE,
        "source_id": "CONF-002",
        "title": "Quy trình triển khai hệ thống Production",
        "content": """
        Quy trình deploy lên môi trường Production phải tuân thủ nghiêm ngặt các bước sau.
        
        Điều kiện tiên quyết:
        - Code đã được review và approve bởi ít nhất 2 engineers
        - Tất cả unit tests và integration tests phải pass
        - QA đã test trên môi trường Staging
        - Product Owner đã sign-off
        
        Các bước triển khai:
        1. Tạo Release branch từ main
        2. Cập nhật version trong package.json và CHANGELOG.md
        3. Chạy full test suite: npm test && npm run e2e
        4. Build Docker image: docker build -t app:v1.2.3 .
        5. Push lên registry: docker push registry.company.com/app:v1.2.3
        6. Cập nhật Helm values file với tag mới
        7. Deploy lên Kubernetes: helm upgrade app ./charts/app
        8. Monitor logs trong 30 phút sau deploy
        9. Thông báo trên kênh #deployments
        
        Rollback nếu có lỗi:
        - helm rollback app 1
        - Thông báo ngay cho team lead và CTO
        
        Liên hệ DevOps: devops@company.com
        """,
        "url": "https://confluence.company.com/deployment",
        "author": "DevOps Team",
        "permissions": ["group_engineering"],
    },
    {
        "source": SourceType.CONFLUENCE,
        "source_id": "CONF-003",
        "title": "Chính sách bảo mật và an toàn thông tin",
        "content": """
        Chính sách bảo mật thông tin của công ty áp dụng cho tất cả nhân viên.
        
        Quy định về mật khẩu:
        - Mật khẩu phải có ít nhất 12 ký tự
        - Bao gồm chữ hoa, chữ thường, số và ký tự đặc biệt
        - Thay đổi mật khẩu mỗi 90 ngày
        - Không dùng chung mật khẩu cho nhiều dịch vụ
        - Sử dụng password manager được công ty cấp phép
        
        Quy định về thiết bị:
        - Không để màn hình mở khi rời khỏi bàn làm việc
        - Khóa máy tính khi không sử dụng (Windows + L)
        - Không cài phần mềm không được phép
        - Báo cáo ngay nếu thiết bị bị mất hoặc bị đánh cắp
        
        Quy định về dữ liệu:
        - Không chia sẻ dữ liệu khách hàng ra bên ngoài
        - Mã hóa tất cả file chứa thông tin nhạy cảm
        - Không lưu dữ liệu công ty trên cloud cá nhân
        
        Vi phạm sẽ bị xử lý theo quy định kỷ luật của công ty.
        Liên hệ Security team: security@company.com
        """,
        "url": "https://confluence.company.com/security-policy",
        "author": "Security Team",
        "permissions": ["group_all_employees"],
    },
    {
        "source": SourceType.JIRA,
        "source_id": "JIRA-001",
        "title": "[KP-101] Tích hợp Slack connector vào Knowledge Platform",
        "content": """
        Tích hợp Slack connector để đồng bộ messages từ các channel quan trọng.
        
        Mô tả:
        Cần implement Slack connector để fetch messages từ các public và private channels,
        sau đó index vào knowledge platform để search được.
        
        Acceptance Criteria:
        - Fetch được messages từ tất cả channels mà bot được invite vào
        - Xử lý được thread replies
        - Parse đúng định dạng mentions, links, code blocks
        - Permissions mapping theo channel membership
        - Rate limit handling theo Slack API guidelines
        
        Technical Notes:
        - Dùng slack-sdk Python library
        - Implement retry logic với exponential backoff
        - Cache channel list để giảm API calls
        
        Priority: High
        Sprint: Sprint 3
        Assignee: Backend Team
        Status: In Progress
        """,
        "url": "https://jira.company.com/browse/KP-101",
        "author": "Product Owner",
        "permissions": ["group_engineering"],
    },
    {
        "source": SourceType.SLACK,
        "source_id": "SLACK-001",
        "title": "#engineering — Thảo luận về architecture",
        "content": """
        [john.doe]: Team ơi, chúng ta nên dùng Qdrant hay Weaviate cho vector DB?
        
        [jane.smith]: Mình vote Qdrant. Performance tốt hơn, filter theo payload flexible hơn.
        Đặc biệt là có thể filter by document_id trước khi search, rất quan trọng cho permission system.
        
        [bob.nguyen]: Đồng ý với Jane. Qdrant cũng có REST API đơn giản, dễ integrate.
        Mình đã test cả 2, Qdrant latency thấp hơn khoảng 30% với dataset 1M vectors.
        
        [john.doe]: OK team, chốt Qdrant nhé. Bob bạn setup docker-compose cho local dev được không?
        
        [bob.nguyen]: Done rồi, mình push lên branch feature/qdrant-setup rồi nhé.
        PR link: https://github.com/company/knowledge-platform/pull/42
        """,
        "url": "https://slack.com/archives/C123456/p1234567890",
        "author": "john.doe",
        "permissions": ["group_engineering"],
    },
    {
        "source": SourceType.SLACK,
        "source_id": "SLACK-002",
        "title": "#general — Thông báo nghỉ lễ",
        "content": """
        [hr.team]: Thông báo lịch nghỉ lễ Tết Nguyên Đán 2026.
        
        Công ty sẽ nghỉ từ ngày 26/01/2026 đến 02/02/2026 (8 ngày).
        Ngày đi làm lại: 03/02/2026 (thứ Ba).
        
        Lưu ý:
        - Hoàn thành bàn giao công việc trước ngày 24/01/2026
        - Đặt Out-of-Office trên email và Slack
        - Các team on-call vẫn trực theo lịch
        
        Chúc mừng năm mới! 🎉🧧
        """,
        "url": "https://slack.com/archives/C789012/p9876543210",
        "author": "hr.team",
        "permissions": ["group_all_employees"],
    },
]


async def seed():
    print("\n" + "="*55)
    print("  Knowledge Platform — Seed Data")
    print("="*55)

    cleaner = TextCleaner()
    chunker = TextChunker()

    async with AsyncSessionLocal() as session:
        repo = DocumentRepository(session)
        vector_index = VectorIndex(session)
        keyword_index = KeywordIndex(session)

        for i, data in enumerate(SAMPLE_DOCUMENTS, 1):
            print(f"\n[{i}/{len(SAMPLE_DOCUMENTS)}] Đang xử lý: {data['title'][:50]}...")

            # Tạo document object
            doc = Document(
                id=str(uuid.uuid4()),
                source=data["source"],
                source_id=data["source_id"],
                title=data["title"],
                content=cleaner.clean(data["content"]),
                url=data["url"],
                author=data["author"],
                created_at=datetime.utcnow(),
                updated_at=datetime.utcnow(),
                metadata={},
                permissions=data["permissions"],
                entities=[],
            )

            # Lưu document
            doc.id = await repo.upsert(doc)
            print(f"   ✅ Saved document: {doc.id}")

            # Chunking
            chunks = chunker.chunk(doc.id, doc.content)
            print(f"   📄 Chunks: {len(chunks)}")

            # Index vector (Qdrant) + keyword (PostgreSQL)
            await vector_index.index_chunks(chunks)
            await keyword_index.index_chunks(chunks)
            print(f"   🔍 Indexed vào Qdrant + PostgreSQL")

        print("\n" + "="*55)
        print(f"✅ Đã nhập {len(SAMPLE_DOCUMENTS)} documents thành công!")
        print("="*55)

        # Seed users và groups để test permission
        await seed_users_groups(session)


async def seed_users_groups(session: AsyncSession):
    from sqlalchemy import text

    print("\n👥 Tạo users và groups mẫu...")

    # Tạo groups
    groups = [
        ("group_all_employees", "All Employees"),
        ("group_engineering",   "Engineering Team"),
        ("group_hr",            "HR Team"),
    ]
    for group_id, group_name in groups:
        await session.execute(
            text("INSERT INTO groups (id, name) VALUES (:id, :name) ON CONFLICT DO NOTHING"),
            {"id": group_id, "name": group_name},
        )

    # Tạo users
    users = [
        ("user_001", "alice@company.com",   "Alice Nguyen", "Password123!", True,  "system_admin"),
        ("user_002", "bob@company.com",     "Bob Tran", "Password123!", False, "pm_po"),
        ("user_003", "charlie@company.com", "Charlie Le", "Password123!", False, "standard"),
    ]
    for user_id, email, name, password, is_admin, role in users:
        await session.execute(
            text("""
                INSERT INTO users (id, email, display_name, password_hash, is_active, is_admin, role)
                VALUES (:id, :email, :name, :password_hash, TRUE, :is_admin, :role)
                ON CONFLICT DO NOTHING
            """),
            {
                "id": user_id,
                "email": email,
                "name": name,
                "password_hash": _hash_password(password),
                "is_admin": is_admin,
                "role": role,
            },
        )

    # Gán users vào groups
    user_groups = [
        ("user_001", "group_all_employees"),
        ("user_001", "group_engineering"),   # Alice: engineering
        ("user_002", "group_all_employees"),
        ("user_002", "group_engineering"),   # Bob: engineering
        ("user_003", "group_all_employees"), # Charlie: chỉ all_employees
    ]
    for user_id, group_id in user_groups:
        await session.execute(
            text("INSERT INTO user_groups (user_id, group_id) VALUES (:uid, :gid) ON CONFLICT DO NOTHING"),
            {"uid": user_id, "gid": group_id},
        )

    await session.commit()

    print("   ✅ Groups: group_all_employees, group_engineering, group_hr")
    print("   ✅ Users:")
    print("      - user_001 (Alice): all_employees + engineering ← thấy TẤT CẢ")
    print("      - user_002 (Bob):   all_employees + engineering ← thấy TẤT CẢ")
    print("      - user_003 (Charlie): chỉ all_employees ← KHÔNG thấy docs engineering")


def _hash_password(password: str) -> str:
    if bcrypt is None:
        raise RuntimeError("bcrypt is required to seed loginable users")
    return bcrypt.hashpw(password.encode(), bcrypt.gensalt()).decode()


if __name__ == "__main__":
    asyncio.run(seed())