import asyncio
import json
import sys
import os

# Add project root to sys.path
sys.path.append(os.getcwd())

from storage.db.db import SyncSessionLocal, DocumentORM
from sqlalchemy import select

def check():
    # Using sync session for script reliability
    with SyncSessionLocal() as s:
        # Check overall jira issues count
        res = s.execute(select(DocumentORM).filter(DocumentORM.source == 'jira'))
        total = res.scalars().all()
        print(f"Total Jira issues: {len(total)}")
        
        # Check first 5 issues metadata
        r = s.execute(select(DocumentORM).filter(DocumentORM.source == 'jira').limit(5))
        for i in r.scalars():
            m = i.metadata_ if hasattr(i, 'metadata_') else i.metadata
            print(f"KEY: {m.get('key')} | STATUS: {m.get('status')} | CAT: {m.get('statusCategory')}")
            print(f"ASSIGNEE: {json.dumps(m.get('assignee'))}")
            print(f"SPRINT: {json.dumps(m.get('sprint'))}")
            print(f"EPIC: {json.dumps(m.get('epic'))}")
            print("-" * 20)

if __name__ == "__main__":
    check()
