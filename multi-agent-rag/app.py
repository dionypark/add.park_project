import json
import uuid
from contextlib import asynccontextmanager
from typing import Optional

from fastapi import FastAPI, HTTPException
from fastapi.responses import StreamingResponse
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


def _chunk_text(chunk) -> str:
    """AIMessageChunk.content가 문자열/블록 리스트 둘 다일 수 있어 텍스트만 뽑아낸다."""
    content = chunk.content
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        return "".join(
            part.get("text", "") for part in content if isinstance(part, dict) and part.get("type") == "text"
        )
    return ""


def _event_source(event: dict) -> Optional[str]:
    """이 이벤트가 어느 노드에서 왔는지: retrieval_agent/cost_agent 서브그래프 안쪽 노드는
    checkpoint_ns의 최상위 접두사(예: "retrieval_agent:<uuid>|agent:<uuid>")로 구분해야
    두 서브그래프의 동일한 이름("agent") 노드가 병렬 실행돼도 섞이지 않는다."""
    metadata = event.get("metadata", {})
    ns = metadata.get("langgraph_checkpoint_ns", "")
    if ns:
        return ns.split(":")[0]
    return metadata.get("langgraph_node")


def _sse(event: str, data: dict) -> str:
    return f"event: {event}\ndata: {json.dumps(data, ensure_ascii=False)}\n\n"


async def _stream_answer(question: str, thread_id: str):
    """최종 답변만 토큰 단위로 스트리밍한다.

    supervisor가 검색/계산 필요 여부를 정하고 나면, 최종 답변이 어느 노드에서 나올지도 정해진다:
    - 둘 다 필요 -> synthesizer가 합쳐서 답함 (retrieval_agent/cost_agent는 병렬로 도는 중간 단계라
      스트리밍 대상에서 제외 - 안 그러면 두 에이전트 텍스트가 섞여 나온다)
    - 하나만 필요 -> 그 에이전트의 결과가 곧 최종 답변이라 그대로 스트리밍
    """
    run_config = {"configurable": {"thread_id": thread_id}}
    final_source = None

    try:
        async for event in _get_graph().astream_events(
            {"messages": [HumanMessage(content=question)]}, config=run_config, version="v2"
        ):
            kind = event["event"]

            if kind == "on_chain_end" and event.get("name") == "supervisor":
                output = event["data"].get("output", {}) or {}
                needs_search = output.get("needs_search", False)
                needs_calculation = output.get("needs_calculation", False)
                if needs_search and needs_calculation:
                    final_source = "synthesizer"
                elif needs_calculation:
                    final_source = "cost_agent"
                else:
                    final_source = "retrieval_agent"
                yield _sse(
                    "phase",
                    {"needs_search": needs_search, "needs_calculation": needs_calculation},
                )

            elif kind == "on_chat_model_stream" and final_source and _event_source(event) == final_source:
                text = _chunk_text(event["data"]["chunk"])
                if text:
                    yield _sse("token", {"text": text})

        yield _sse("done", {"thread_id": thread_id})
    except Exception as e:  # noqa: BLE001
        yield _sse("error", {"message": str(e)})


@app.post("/query/stream")
async def query_stream(request: QueryRequest):
    if not request.question.strip():
        raise HTTPException(status_code=400, detail="question은 비어 있을 수 없습니다.")

    thread_id = request.thread_id or str(uuid.uuid4())
    return StreamingResponse(
        _stream_answer(request.question, thread_id),
        media_type="text/event-stream",
        headers={"X-Thread-Id": thread_id, "Cache-Control": "no-cache"},
    )
