import uuid
from contextlib import asynccontextmanager
from typing import Optional

from fastapi import FastAPI, HTTPException
from langchain_core.messages import HumanMessage
from pydantic import BaseModel

from graph import _last_text, build_agent_graph

_graph = None


def _get_graph():
    global _graph
    if _graph is None:
        _graph = build_agent_graph()
    return _graph


@asynccontextmanager
async def lifespan(app: FastAPI):
    # 서버가 요청을 받기 시작하기 전에 무거운 초기화(임베딩 모델, 벡터DB, LLM)를 미리 끝내둔다.
    _get_graph()
    yield


app = FastAPI(title="Multi-Agent RAG — AWS 서비스 선택/비용 최적화 어드바이저", lifespan=lifespan)


class QueryRequest(BaseModel):
    question: str
    thread_id: Optional[str] = None


class QueryResponse(BaseModel):
    answer: str
    thread_id: str
    needs_search: bool
    needs_calculation: bool


@app.get("/health")
def health():
    return {"status": "ok"}


@app.post("/query", response_model=QueryResponse)
def query(request: QueryRequest):
    if not request.question.strip():
        raise HTTPException(status_code=400, detail="question은 비어 있을 수 없습니다.")

    thread_id = request.thread_id or str(uuid.uuid4())
    result = _get_graph().invoke(
        {"messages": [HumanMessage(content=request.question)]},
        config={"configurable": {"thread_id": thread_id}},
    )
    answer = _last_text(result["messages"])
    return QueryResponse(
        answer=answer,
        thread_id=thread_id,
        needs_search=result.get("needs_search", False),
        needs_calculation=result.get("needs_calculation", False),
    )
