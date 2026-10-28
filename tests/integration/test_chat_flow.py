# tests/integration/test_chat_flow.py
import pytest
from src.core.api.schemas import ChatRequest
from src.core.services.chat_service import ChatService


@pytest.mark.asyncio
async def test_chat_remembers_session(db, llm, retriever, settings):
    svc = ChatService(db=db, llm=llm, retriever=retriever, settings=settings)

    r1 = await svc.handle(ChatRequest(message="Привет"))
    r2 = await svc.handle(
        ChatRequest(message="А что было раньше?", session_id=r1.session_id)
    )
    assert r1.session_id == r2.session_id
    assert r2.message_id > r1.message_id
