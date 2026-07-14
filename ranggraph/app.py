import uuid
from contextlib import asynccontextmanager
from typing import Optional

from fastapi import FastAPI, HTTPException
from langchain_core.messages import HumanMessage
from pydantic import BaseModel

from graph import build_agent_graph

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


app = FastAPI(title="AWS 서비스 선택/비용 최적화 어드바이저 (LangGraph 에이전트)", lifespan=lifespan)


class QueryRequest(BaseModel):
    question: str
    thread_id: Optional[str] = None


class QueryResponse(BaseModel):
    answer: str
    thread_id: str


def _content_to_text(content) -> str:
    # 최신 Claude 모델은 content를 문자열 대신 content block 리스트로 반환할 수 있다.
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        parts = []
        for part in content:
            if isinstance(part, str):
                parts.append(part)
            elif isinstance(part, dict) and part.get("type") == "text":
                parts.append(part.get("text", ""))
        return "".join(parts)
    return str(content)


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
    answer = _content_to_text(result["messages"][-1].content)
    return QueryResponse(answer=answer, thread_id=thread_id)
