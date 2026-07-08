"""ChromaDB에 저장된 AWS 문서를 검색해 Claude로 답변을 생성한다."""
import sys

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


def _get_collection():
    client = chromadb.PersistentClient(path=config.CHROMA_DB_DIR)
    return client.get_collection(name=config.COLLECTION_NAME)


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
