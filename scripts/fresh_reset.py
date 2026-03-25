import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import shutil
import asyncio
import uuid
import bcrypt
from sqlalchemy import text
from storage.db.db import AsyncSessionLocal, Base, engine
from storage.vector.vector_store import get_qdrant
from config.settings import settings

async def reset_database():
    print("\n🚨 BẮT ĐẦU QUÁ TRÌNH RESET HỆ THỐNG (FRESH START) 🚨")
    print("="*50)

    # 1. Truncate toàn bộ PostgreSQL
    async with engine.begin() as conn:
        # Lấy danh sách tất cả các bảng trong schema public
        result = await conn.execute(text(
            "SELECT table_name FROM information_schema.tables WHERE table_schema = 'public' AND table_type = 'BASE TABLE';"
        ))
        tables = [row[0] for row in result.all()]
        
        if tables:
            tables_str = ", ".join(tables)
            print(f"🧹 Đang truncate các bảng Postgres: {tables_str}")
            await conn.execute(text(f"TRUNCATE {tables_str} CASCADE;"))
            print("✅ Đã xóa sạch dữ liệu Postgres.")
        else:
            print("ℹ️ Không tìm thấy bảng nào để xóa.")

    # 2. Xóa Qdrant (Vector DB)
    try:
        print("🧹 Đang dọn dẹp Vector DB (Qdrant)...")
        qdrant = get_qdrant()
        collections = [settings.QDRANT_COLLECTION, "semantic_cache"]
        for col in collections:
            try:
                qdrant.delete_collection(collection_name=col)
                print(f"  - Đã xóa collection: {col}")
            except Exception as e:
                print(f"  - Bỏ qua collection {col}: {e}")
        print("✅ Đã xử lý xong dữ liệu Qdrant.")
    except Exception as e:
        print(f"⚠️ Lỗi khi kết nối Qdrant: {e}")

    # 3. Xóa Local Assets
    assets_dir = settings.ASSETS_DIR
    if os.path.exists(assets_dir):
        print(f"🧹 Đang xóa thư mục assets: {assets_dir}")
        try:
            # Xóa các file bên trong thay vì xóa chính thư mục nếu muốn giữ folder
            for filename in os.listdir(assets_dir):
                file_path = os.path.join(assets_dir, filename)
                try:
                    if os.path.isfile(file_path) or os.path.islink(file_path):
                        os.unlink(file_path)
                    elif os.path.is_dir(file_path):
                        shutil.rmtree(file_path)
                except Exception as e:
                    print(f'  - Không thể xóa {file_path}. Lỗi: {e}')
            print("✅ Đã xóa sạch các tệp tin assets.")
        except Exception as e:
            print(f"⚠️ Lỗi khi dọn dẹp assets: {e}")
    else:
        print(f"ℹ️ Thư mục assets không tồn tại ({assets_dir})")

    # 4. Tạo tài khoản Admin mới
    async with AsyncSessionLocal() as session:
        admin_email = os.getenv("ADMIN_EMAIL", "tuongnm@technica.ai")
        admin_pass = os.getenv("ADMIN_PASSWORD", "123456")
        hashed_pw = bcrypt.hashpw(admin_pass.encode(), bcrypt.gensalt()).decode()
        user_id = f"user_admin_{uuid.uuid4().hex[:6]}"

        print(f"👤 Đang tạo tài khoản System Admin: {admin_email}...")

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

        # Cấp quyền cho Admin vào một group mặc định
        group_id = "group_system_admins"
        await session.execute(
            text("INSERT INTO groups (id, name) VALUES (:id, :name) ON CONFLICT DO NOTHING"),
            {"id": group_id, "name": "System Administrators"}
        )
        await session.execute(
            text("INSERT INTO user_groups (user_id, group_id) VALUES (:uid, :gid) ON CONFLICT DO NOTHING"),
            {"uid": user_id, "gid": group_id}
        )

        # Seed default prompts (để hệ thống có thể hoạt động ngay)
        from persistence.skill_prompt_repository import SkillPromptRepository
        repo = SkillPromptRepository(session)
        await repo.seed_defaults()

        await session.commit()
        print("\n🎉 HOÀN TẤT RESET!")
        print("="*50)
        print(f"Tài khoản : {admin_email}")
        print(f"Mật khẩu  : {admin_pass}")
        print("="*50 + "\n")

if __name__ == "__main__":
    asyncio.run(reset_database())
