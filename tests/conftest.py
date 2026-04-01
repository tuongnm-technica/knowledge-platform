import sys
from unittest.mock import MagicMock

# Global mocks for missing dependencies during test collection
_mock_modules = [
    "qdrant_client", "qdrant_client.http", "qdrant_client.http.models",
    "atlassian", "atlassian.confluence", 
    "slack_sdk", "slack_sdk.web", "slack_sdk.web.async_client", "slack_sdk.errors",
    "smbprotocol", "smbclient",
    "google.oauth2", "google_auth_oauthlib", "googleapiclient", "googleapiclient.discovery", "googleapiclient.http", "googleapiclient.errors",
    "google.auth", "google.auth.transport.requests",
    "arq", "arq.connections"
]

# Identify which are packages (anything that is a parent of another module in the list)
_packages = set()
for mod in _mock_modules:
    parts = mod.split(".")
    for i in range(len(parts)):
        pkg = ".".join(parts[:i+1])
        _packages.add(pkg)

for mod in sorted(list(_packages)): # Sort to ensure parents are created first
    if mod not in sys.modules:
        m = MagicMock()
        m.__name__ = mod
        m.__spec__ = None
        # If it's a parent of something else OR explicitly in our package list, give it __path__
        has_sub = any(other.startswith(mod + ".") for other in _mock_modules)
        if has_sub or mod in ["qdrant_client", "atlassian", "slack_sdk", "arq"]:
            m.__path__ = []
        sys.modules[mod] = m

import pytest
import asyncio
from unittest.mock import MagicMock
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker, AsyncSession
from storage.db.db import Base

@pytest.fixture(scope="session")
def event_loop():
    """Create an instance of the default event loop for each test case."""
    try:
        loop = asyncio.get_event_loop()
    except RuntimeError:
        loop = asyncio.new_event_loop()
    yield loop
    loop.close()

@pytest.fixture
def mock_httpx_client(mocker):
    """Fixture to mock httpx.AsyncClient."""
    mock = mocker.patch("httpx.AsyncClient", autospec=True)
    instance = mock.return_value
    instance.__aenter__.return_value = instance
    instance.__aexit__.return_value = None
    return instance

@pytest.fixture
async def db_session():
    """Fixture to provide an in-memory SQLite async session."""
    engine = create_async_engine("sqlite+aiosqlite:///:memory:", echo=False)
    async_session = async_sessionmaker(engine, expire_on_commit=False, class_=AsyncSession)
    
    async with engine.begin() as conn:
        from storage.db.db import LLMModelORM, ModelBindingORM
        # We only create tables needed for current repository tests to avoid conflicts
        await conn.run_sync(LLMModelORM.metadata.create_all, tables=[LLMModelORM.__table__, ModelBindingORM.__table__])
        
    async with async_session() as session:
        yield session
        
    await engine.dispose()
