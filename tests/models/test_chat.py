import uuid
from models.chat import ChatSession, ChatMessage, ChatJob

def test_chat_session_instantiation():
    session = ChatSession(
        user_id="user123",
        title="Test Session"
    )
    assert session.user_id == "user123"
    assert session.title == "Test Session"

def test_chat_message_instantiation():
    session_id = str(uuid.uuid4())
    msg = ChatMessage(
        session_id=session_id,
        role="user",
        content="Hello assistant"
    )
    assert msg.role == "user"
    assert msg.content == "Hello assistant"
    assert msg.session_id == session_id

def test_chat_job_instantiation():
    job = ChatJob(
        user_id="user123",
        question="What is the weather?",
        status="queued",
        progress=0
    )
    assert job.status == "queued"
    assert job.progress == 0
