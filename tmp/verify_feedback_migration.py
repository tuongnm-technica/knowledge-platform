import asyncio
from sqlalchemy import text
from storage.db.db import engine

async def verify_migration():
    """
    Kiểm tra xem các cột mới của Feedback Loop đã được tạo thành công trong Database chưa.
    """
    print("🔍 Kiểm tra Database Migration...")
    
    async with engine.connect() as conn:
        # Lấy danh sách cột của query_logs
        result = await conn.execute(text("""
            SELECT column_name, data_type 
            FROM information_schema.columns 
            WHERE table_name = 'query_logs'
        """))
        columns = {row[0]: row[1] for row in result.all()}
        
        expected = ['answer', 'sources_used', 'edges_used', 'feedback', 'feedback_at']
        missing = [c for c in expected if c not in columns]
        
        if not missing:
            print("✅ Thành công! Các cột Feedback Loop đã sẵn sàng:")
            for col in expected:
                print(f"   - {col} ({columns[col]})")
        else:
            print(f"❌ Lỗi! Thiếu các cột: {missing}")
            print("👉 Hãy khởi động lại API server để chạy `create_tables()`.")

if __name__ == "__main__":
    asyncio.run(verify_migration())
