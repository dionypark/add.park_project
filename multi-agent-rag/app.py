import json
import uuid
from contextlib import asynccontextmanager
from typing import Optional

import aiosqlite
from fastapi import Depends, FastAPI, Header, HTTPException
from fastapi.responses import StreamingResponse
from langchain_core.messages import AIMessage, HumanMessage
from langgraph.checkpoint.sqlite.aio import AsyncSqliteSaver
from pydantic import BaseModel

import auth
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
    auth.init_db()

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


def _require_user(authorization: Optional[str] = Header(None)) -> dict:
    """Authorization: Bearer <token> 헤더에서 로그인 사용자를 뽑는다. 없거나 무효면 401."""
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="로그인이 필요합니다.")
    user = auth.get_user(authorization.removeprefix("Bearer "))
    if user is None:
        raise HTTPException(status_code=401, detail="세션이 만료됐거나 유효하지 않습니다. 다시 로그인해주세요.")
    return user


class SignupRequest(BaseModel):
    username: str
    password: str


class AuthResponse(BaseModel):
    token: str
    username: str


@app.post("/auth/signup", response_model=AuthResponse)
def signup(request: SignupRequest):
    try:
        token = auth.signup(request.username, request.password)
    except (auth.UsernameTakenError, auth.InvalidCredentialsError) as e:
        raise HTTPException(status_code=400, detail=str(e))
    return AuthResponse(token=token, username=request.username.strip())


@app.post("/auth/login", response_model=AuthResponse)
def login(request: SignupRequest):
    try:
        token = auth.login(request.username, request.password)
    except auth.InvalidCredentialsError as e:
        raise HTTPException(status_code=401, detail=str(e))
    return AuthResponse(token=token, username=request.username.strip())


@app.post("/auth/logout")
def logout(authorization: Optional[str] = Header(None)):
    if authorization and authorization.startswith("Bearer "):
        auth.logout(authorization.removeprefix("Bearer "))
    return {"status": "ok"}


@app.get("/auth/me")
def me(user: dict = Depends(_require_user)):
    return user


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
def query(request: QueryRequest, user: dict = Depends(_require_user)):
    if not request.question.strip():
        raise HTTPException(status_code=400, detail="question은 비어 있을 수 없습니다.")

    thread_id = request.thread_id or str(uuid.uuid4())
    auth.record_thread(user["id"], thread_id)
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
def get_thread(thread_id: str, user: dict = Depends(_require_user)):
    """특정 thread_id의 전체 대화 기록. 서랍에서 클릭해 다시 열 때 씀.

    로그인 기반으로 바뀌면서 소유권도 같이 확인한다 - user_threads에 (내 user_id, 이
    thread_id) 조합이 없으면 그 thread_id를 알아도(추측해도) 못 열게 막는다. 로그인 전에는
    thread_id(랜덤 UUID)를 아는 사람만 열 수 있다는 게 유일한 방어선이었는데, 지금은 거기에
    "그리고 실제 소유자여야 한다"는 조건이 하나 더 생긴 것."""
    if thread_id not in auth.list_user_thread_ids(user["id"]):
        raise HTTPException(status_code=403, detail="이 대화에 접근할 권한이 없습니다.")
    messages = _thread_messages(thread_id)
    if not messages:
        raise HTTPException(status_code=404, detail="해당 thread_id의 대화를 찾을 수 없습니다.")
    return ThreadHistory(thread_id=thread_id, messages=[ThreadMessage(**m) for m in messages])


class ThreadSummary(BaseModel):
    thread_id: str
    preview: str


@app.get("/my-threads", response_model=list[ThreadSummary])
def my_threads(user: dict = Depends(_require_user)):
    """로그인한 사용자 본인이 만든 대화 목록만 (최근 순). 서랍 UI가 이걸 호출한다."""
    summaries = []
    for thread_id in auth.list_user_thread_ids(user["id"]):
        messages = _thread_messages(thread_id)
        first_user_msg = next((m["content"] for m in messages if m["role"] == "user"), "")
        preview = first_user_msg[:40] + ("..." if len(first_user_msg) > 40 else "")
        summaries.append(ThreadSummary(thread_id=thread_id, preview=preview or "(빈 대화)"))
    return summaries


@app.delete("/threads/{thread_id}")
def delete_thread(thread_id: str, user: dict = Depends(_require_user)):
    """서랍 목록에서 삭제. 본인 것이 아니면(또는 이미 없으면) 404."""
    if not auth.delete_thread(user["id"], thread_id):
        raise HTTPException(status_code=404, detail="해당 대화를 찾을 수 없습니다.")
    return {"status": "ok"}


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
async def query_stream(request: QueryRequest, user: dict = Depends(_require_user)):
    if not request.question.strip():
        raise HTTPException(status_code=400, detail="question은 비어 있을 수 없습니다.")

    thread_id = request.thread_id or str(uuid.uuid4())
    auth.record_thread(user["id"], thread_id)
    return StreamingResponse(
        _stream_answer(request.question, thread_id),
        media_type="text/event-stream",
        headers={"X-Thread-Id": thread_id, "Cache-Control": "no-cache"},
    )
