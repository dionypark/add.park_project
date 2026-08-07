import json
import uuid
from contextlib import asynccontextmanager
from typing import Optional

import aiosqlite
from fastapi import FastAPI, HTTPException
from fastapi.responses import StreamingResponse
from langchain_core.messages import AIMessage, HumanMessage
from langgraph.checkpoint.sqlite.aio import AsyncSqliteSaver
from pydantic import BaseModel

import pricing
from graph import CHECKPOINT_DB_PATH, _last_text, build_agent_graph

_graph = None


def _get_graph():
    if _graph is None:
        raise RuntimeError("그래프가 아직 초기화되지 않았습니다 (lifespan이 안 끝난 상태에서 호출됨).")
    return _graph


@asynccontextmanager
async def lifespan(app: FastAPI):
    # /query/stream이 astream_events()(비동기)를 쓰기 때문에, 동기 전용인 SqliteSaver로는
    # 체크포인트를 못 남기고 에러가 난다(SqliteSaver does not support async methods).
    # 그래서 여기서는 비동기 버전인 AsyncSqliteSaver를 직접 만들어서 넘긴다.
    global _graph
    conn = await aiosqlite.connect(CHECKPOINT_DB_PATH)
    checkpointer = AsyncSqliteSaver(conn)
    await checkpointer.setup()
    _graph = build_agent_graph(checkpointer=checkpointer)

    # EC2 요금 캐시가 없거나 오래됐으면 첫 사용자 요청이 아니라 서버 시작 시점에 미리
    # 받아둔다 - 안 그러면 첫 EC2 관련 질문을 한 사용자가 480MB 다운로드를 그대로
    # 떠안게 되어 응답이 수십 초~몇 분씩 멎은 것처럼 보인다.
    if pricing.fetch_ec2_prices() is None:
        print("[startup] EC2 요금 캐시 준비 실패 - calculate_cost가 하드코딩된 근사치로 폴백합니다.")

    yield
    await conn.close()


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


class ThreadMessage(BaseModel):
    role: str
    content: str


class ThreadHistory(BaseModel):
    thread_id: str
    messages: list[ThreadMessage]


def _thread_messages(thread_id: str) -> list[dict]:
    state = _get_graph().get_state({"configurable": {"thread_id": thread_id}})
    history = []
    for msg in state.values.get("messages", []):
        if isinstance(msg, HumanMessage):
            text = msg.content if isinstance(msg.content, str) else _last_text([msg])
            if text:
                history.append({"role": "user", "content": text})
        elif isinstance(msg, AIMessage):
            text = _last_text([msg])
            if text:
                history.append({"role": "assistant", "content": text})
    return history


@app.get("/threads/{thread_id}", response_model=ThreadHistory)
def get_thread(thread_id: str):
    """특정 thread_id의 전체 대화 기록. 서랍에서 클릭해 다시 열 때 씀.

    일부러 전체 thread_id를 나열하는 엔드포인트(GET /threads)를 두지 않았다 - 로그인 없는
    구조라, 만약 그런 엔드포인트가 있으면 누구나 다른 사람의 질문 미리보기를 볼 수 있게 된다.
    thread_id(랜덤 UUID)를 아는 사람만 그 대화를 열 수 있는 게 지금 구조의 유일한 방어선이라,
    그 값은 각 클라이언트(Streamlit 세션)가 직접 기억해서 물어봐야 한다."""
    messages = _thread_messages(thread_id)
    if not messages:
        raise HTTPException(status_code=404, detail="해당 thread_id의 대화를 찾을 수 없습니다.")
    return ThreadHistory(thread_id=thread_id, messages=[ThreadMessage(**m) for m in messages])


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
