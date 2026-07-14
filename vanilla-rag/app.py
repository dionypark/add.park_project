from contextlib import asynccontextmanager

import chromadb.errors
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel

import config
from rag_query import answer_question, warm_up


@asynccontextmanager
async def lifespan(app: FastAPI):
    # 서버가 요청을 받기 시작하기 전에 무거운 초기화를 미리 끝내둔다.
    warm_up()
    yield


app = FastAPI(title="AWS 서비스 선택/비용 최적화 어드바이저", lifespan=lifespan)


class AskRequest(BaseModel):
    question: str
    top_k: int = config.TOP_K


class Source(BaseModel):
    source: str
    header: str


class AskResponse(BaseModel):
    question: str
    answer: str
    sources: list[Source]


@app.get("/health")
def health():
    return {"status": "ok"}


@app.post("/ask", response_model=AskResponse)
def ask(request: AskRequest):
    if not request.question.strip():
        raise HTTPException(status_code=400, detail="question은 비어 있을 수 없습니다.")
    try:
        return answer_question(request.question, top_k=request.top_k)
    except chromadb.errors.NotFoundError:
        raise HTTPException(
            status_code=503,
            detail="벡터DB 컬렉션이 없습니다. build_vectordb.py를 먼저 실행하세요.",
        )
