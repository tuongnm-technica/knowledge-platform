import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import asyncio
import uuid
import bcrypt
from sqlalchemy import text
from storage.db.db import AsyncSessionLocal, Base, engine
from storage.vector.vector_store import get_qdrant
from config.settings import settings

async def reset_database():
    print("\n🚨 BẮT ĐẦU QUÁ TRÌNH RESET HỆ THỐNG 🚨")
    print("="*50)

    # 1. Truncate toàn bộ PostgreSQL
    async with engine.begin() as conn:
        tables = [table.name for table in Base.metadata.sorted_tables]
        if tables:
            tables_str = ", ".join(tables)
            print(f"🧹 Đang truncate các bảng Postgres...")
            # Lệnh CASCADE sẽ dọn sạch cả các bảng có quan hệ khóa ngoại (Foreign Key)
            await conn.execute(text(f"TRUNCATE {tables_str} CASCADE;"))
            print("✅ Đã xóa sạch dữ liệu Postgres.")

    # 2. Xóa Qdrant (Vector DB)
    try:
        print("🧹 Đang dọn dẹp Vector DB (Qdrant)...")
        qdrant = get_qdrant()
        qdrant.delete_collection(collection_name=settings.QDRANT_COLLECTION)
        qdrant.delete_collection(collection_name="semantic_cache")
        print("✅ Đã xóa sạch dữ liệu Qdrant.")
    except Exception as e:
        print(f"⚠️ Bỏ qua Qdrant (có thể collection chưa được tạo): {e}")

    # 3. Tạo tài khoản Admin
    async with AsyncSessionLocal() as session:
        admin_email = os.getenv("ADMIN_EMAIL", "tuongnm@technica.ai")
        admin_pass = os.getenv("ADMIN_PASSWORD", "12345678")
        hashed_pw = bcrypt.hashpw(admin_pass.encode(), bcrypt.gensalt()).decode()
        user_id = f"user_admin_{uuid.uuid4().hex[:6]}"

        print(f"👤 Đang tạo tài khoản System Admin...")

        await session.execute(
            text("""
                INSERT INTO users (id, email, display_name, password_hash, is_active, is_admin, role)
                VALUES (:id, :email, :name, :hash, TRUE, TRUE, 'system_admin')
            """),
            {
                "id": user_id,
                "email": admin_email,
                "name": "Tường NM (Admin)",
                "hash": hashed_pw
            }
        )

        # Cấp quyền cho Admin vào một group mặc định để có thể bắt đầu sử dụng ngay
        group_id = "group_system_admins"
        await session.execute(
            text("INSERT INTO groups (id, name) VALUES (:id, :name) ON CONFLICT DO NOTHING"),
            {"id": group_id, "name": "System Administrators"}
        )
        await session.execute(
            text("INSERT INTO user_groups (user_id, group_id) VALUES (:uid, :gid) ON CONFLICT DO NOTHING"),
            {"uid": user_id, "gid": group_id}
        )

        await session.commit()
        print("\n🎉 HOÀN TẤT RESET!")
        print("="*50)
        print(f"Tài khoản : {admin_email}")
        print(f"Mật khẩu  : {admin_pass}")
        print("="*50 + "\n")

if __name__ == "__main__":
    asyncio.run(reset_database())