import asyncio
import sys
import os
import json

# Add the project root to sys.path to allow imports
sys.path.append(os.getcwd())

from storage.db.db import AsyncSessionLocal
from sqlalchemy import text

async def check_logs():
    output_path = r"d:\CodeProject\knowledge-platform\tmp\debug_zoom_output.txt"
    with open(output_path, "w", encoding="utf-8") as f:
        async with AsyncSessionLocal() as session:
            try:
                # Check last 10 sync logs for Zoom
                res = await session.execute(text(
                    "SELECT id, connector, status, errors, fetched, indexed, started_at, finished_at "
                    "FROM sync_logs "
                    "WHERE connector LIKE 'zoom:%' "
                    "ORDER BY id DESC "
                    "LIMIT 10"
                ))
                rows = res.mappings().all()
                f.write("--- ZOOM SYNC LOGS (Last 10) ---\n")
                for r in rows:
                    d = dict(r)
                    for k, v in d.items():
                        if v and hasattr(v, 'isoformat'):
                            d[k] = v.isoformat()
                    f.write(json.dumps(d, indent=2) + "\n")
                
                # Check ALL Zoom connector instances
                res = await session.execute(text(
                    "SELECT id, name, username, secret, extra FROM connector_instances WHERE connector_type = 'zoom'"
                ))
                instances = res.mappings().all()
                f.write("\n--- ZOOM INSTANCES ---\n")
                for inst in instances:
                    d = dict(inst)
                    # Mask secret
                    s = d.get('secret')
                    d['secret_present'] = bool(s)
                    d['secret_len'] = len(s) if s else 0
                    d.pop('secret', None)
                    f.write(json.dumps(d, indent=2) + "\n")
                    
            except Exception as e:
                f.write(f"Error checking logs: {e}\n")
    print(f"Debug info written to {output_path}")

if __name__ == "__main__":
    asyncio.run(check_logs())
