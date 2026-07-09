"""LangChain LCEL 체인으로 AWS 문서를 검색해 Claude로 답변을 생성한다."""
import sys
import threading

from langchain_anthropic import ChatAnthropic
from langchain_core.output_parsers import StrOutputParser
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.runnables import RunnableParallel, RunnablePassthrough

import config
from build_vectordb import build_vectordb

PROMPT = ChatPromptTemplate.from_messages(
    [
        (
            "system",
            "당신은 AWS 서비스 선택과 비용 최적화를 도와주는 어드바이저입니다. "
            "아래 참고 문서만 근거로 답변하세요. 문서에 없는 내용은 추측하지 말고 모른다고 답하세요.\n\n{context}",
        ),
        ("human", "{question}"),
    ]
)

# 무겁게 초기화되는 것(임베딩 모델 로드, Chroma 클라이언트, LLM 클라이언트)만 프로세스당 한 번 캐싱한다.
# 동시 요청에서 중복 초기화가 안 되도록 락으로 감쌈(체크-후-실행 경쟁 조건 방지).
_vectorstore = None
_llm = None
_init_lock = threading.Lock()


def _get_vectorstore():
    global _vectorstore
    if _vectorstore is None:
        with _init_lock:
            if _vectorstore is None:
                _vectorstore = build_vectordb()
    return _vectorstore


def _get_llm():
    global _llm
    if _llm is None:
        with _init_lock:
            if _llm is None:
                _llm = ChatAnthropic(model=config.GENERATION_MODEL)
    return _llm


def warm_up() -> None:
    """무거운 초기화(임베딩 모델, 벡터DB, LLM 클라이언트)를 미리 끝내둔다. 서버 시작 시 호출."""
    _get_vectorstore()
    _get_llm()


def format_docs(docs) -> str:
    return "\n\n".join(
        f"[출처: {d.metadata.get('source', '')} - {d.metadata.get('header', '')}]\n{d.page_content}"
        for d in docs
    )


def build_chain(top_k: int = config.TOP_K):
    """top_k는 검색 개수만 바꾸는 가벼운 조립이라 매 호출마다 새로 만들어도 무겁지 않다.
    (임베딩 모델/Chroma/LLM 로딩 같은 무거운 부분은 _get_vectorstore/_get_llm이 이미 캐싱함)"""
    retriever = _get_vectorstore().as_retriever(search_kwargs={"k": top_k})
    llm = _get_llm()

    generate_step = (
        (lambda x: {"context": format_docs(x["context"]), "question": x["question"]})
        | PROMPT
        | llm
        | StrOutputParser()
    )

    return RunnableParallel(context=retriever, question=RunnablePassthrough()) | RunnablePassthrough.assign(
        answer=generate_step
    )


def answer_question(question: str, top_k: int = config.TOP_K) -> dict:
    result = build_chain(top_k).invoke(question)
    if not result["context"]:
        raise RuntimeError("벡터DB에 문서가 없습니다. build_vectordb.py를 먼저 실행하세요.")
    return {
        "question": question,
        "answer": result["answer"],
        "sources": [
            {"source": d.metadata.get("source", ""), "header": d.metadata.get("header", "")}
            for d in result["context"]
        ],
    }


if __name__ == "__main__":
    q = " ".join(sys.argv[1:]) or "트래픽 적은 개인 프로젝트인데 뭐 써야해?"
    result = answer_question(q)
    print(f"질문: {result['question']}\n")
    print(f"답변:\n{result['answer']}\n")
    print("출처:")
    for s in result["sources"]:
        print(f"  - {s['source']} ({s['header']})")
