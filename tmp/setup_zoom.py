import asyncio
import uuid
import json
from datetime import datetime
from sqlalchemy import text
from storage.db.db import AsyncSessionLocal

ACCOUNT_ID = "JHteZboYTE-6yTrbD6XG4g"
CLIENT_ID = "eWjnDm7YR7iYgAQu1xqKgw"
CLIENT_SECRET = "YR9EvnKlviZT2bv4YthMV1zVPL878sL4"

async def setup():
    async with AsyncSessionLocal() as session:
        # Check for existing Zoom instance
        res = await session.execute(text("SELECT id FROM connector_instances WHERE connector_type = 'zoom' LIMIT 1"))
        row = res.fetchone()
        
        extra = json.dumps({'client_id': CLIENT_ID})
        now = datetime.utcnow()

        if row:
            # Update existing
            instance_id = row[0]
            await session.execute(text("""
                UPDATE connector_instances 
                SET username = :acc, secret = :sec, extra = CAST(:ext AS JSON), updated_at = :now
                WHERE id = :id
            """), {'acc': ACCOUNT_ID, 'sec': CLIENT_SECRET, 'ext': extra, 'now': now, 'id': instance_id})
            print(f'Updated existing Zoom instance: {instance_id}')
        else:
            # Insert new
            instance_id = str(uuid.uuid4())
            await session.execute(text("""
                INSERT INTO connector_instances (id, connector_type, name, auth_type, username, secret, extra, created_at, updated_at)
                VALUES (:id, 'zoom', 'Zoom Cloud', 'token', :acc, :sec, CAST(:ext AS JSON), :now, :now)
            """), {'id': instance_id, 'acc': ACCOUNT_ID, 'sec': CLIENT_SECRET, 'ext': extra, 'now': now})
            print(f'Created new Zoom instance: {instance_id}')

        # Ensure config exists and is enabled
        connector_key = f'zoom:{instance_id}'
        await session.execute(text("""
            INSERT INTO connector_configs (connector, enabled, auto_sync, schedule_hour, schedule_minute, schedule_tz, selection)
            VALUES (:k, TRUE, TRUE, 4, 0, 'Asia/Ho_Chi_Minh', '{}'::json)
            ON CONFLICT (connector) DO UPDATE SET enabled = TRUE, auto_sync = TRUE
        """), {'k': connector_key})
        
        await session.commit()
        print('Zoom configuration completed successfully.')

if __name__ == "__main__":
    asyncio.run(setup())
