"""ChromaDB에 저장된 AWS 문서를 검색해 Claude로 답변을 생성한다."""
import sys
import threading

import chromadb

import config

PROMPT_TEMPLATE = """당신은 AWS 서비스 선택과 비용 최적화를 도와주는 어드바이저입니다.
아래 참고 문서만 근거로 답변하세요. 문서에 없는 내용은 추측하지 말고 모른다고 답하세요.

[참고 문서]
{context}

[질문]
{question}

[답변]
"""

# chromadb 연결은 무거운 편이라 프로세스당 한 번만 캐싱한다. (동시 요청 경쟁 조건 방지용 락 포함)
_collection = None
_collection_lock = threading.Lock()


def _get_collection():
    global _collection
    if _collection is None:
        with _collection_lock:
            if _collection is None:
                client = chromadb.PersistentClient(path=config.CHROMA_DB_DIR)
                _collection = client.get_collection(name=config.COLLECTION_NAME)
    return _collection


def warm_up() -> None:
    """무거운 초기화(임베딩 모델, ChromaDB 연결)를 미리 끝내둔다. 서버 시작 시 호출.
    벡터DB가 아직 안 만들어져 있어도(build_vectordb.py 실행 전) 서버 자체는 뜨도록 예외를 삼킨다."""
    config.get_embedder()
    try:
        _get_collection()
    except chromadb.errors.NotFoundError:
        pass


def embed_query(text: str) -> list[float]:
    return config.get_embedder().encode(text, normalize_embeddings=True).tolist()


def retrieve(question: str, top_k: int = config.TOP_K) -> list[dict]:
    collection = _get_collection()
    query_embedding = embed_query(question)
    result = collection.query(query_embeddings=[query_embedding], n_results=top_k)

    hits = []
    for text, metadata, distance in zip(
        result["documents"][0], result["metadatas"][0], result["distances"][0]
    ):
        hits.append({"text": text, "source": metadata["source"], "header": metadata["header"], "distance": distance})
    return hits


def build_prompt(question: str, hits: list[dict]) -> str:
    context = "\n\n".join(
        f"[출처: {h['source']} - {h['header']}]\n{h['text']}" for h in hits
    )
    return PROMPT_TEMPLATE.format(context=context, question=question)


def answer_question(question: str, top_k: int = config.TOP_K) -> dict:
    hits = retrieve(question, top_k)
    prompt = build_prompt(question, hits)
    response = config.anthropic_client.messages.create(
        model=config.GENERATION_MODEL,
        max_tokens=1024,
        messages=[{"role": "user", "content": prompt}],
    )
    answer_text = next(block.text for block in response.content if block.type == "text")
    return {
        "question": question,
        "answer": answer_text,
        "sources": [{"source": h["source"], "header": h["header"]} for h in hits],
    }


if __name__ == "__main__":
    q = " ".join(sys.argv[1:]) or "트래픽 적은 개인 프로젝트인데 뭐 써야해?"
    result = answer_question(q)
    print(f"질문: {result['question']}\n")
    print(f"답변:\n{result['answer']}\n")
    print("출처:")
    for s in result["sources"]:
        print(f"  - {s['source']} ({s['header']})")
