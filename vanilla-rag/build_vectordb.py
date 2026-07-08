"""AWS 문서를 청킹하여 로컬 임베딩 모델로 임베딩하고 ChromaDB에 영구 저장한다.

이미 컬렉션에 데이터가 있으면 재임베딩을 건너뛴다.
"""
import glob
import os

import chromadb

import config
from chunking import chunk_markdown


def load_documents(data_dir: str) -> list[tuple[str, str]]:
    """(파일명, 텍스트) 튜플 목록을 반환한다."""
    paths = sorted(
        glob.glob(os.path.join(data_dir, "*.md"))
        + glob.glob(os.path.join(data_dir, "*.txt"))
    )
    docs = []
    for path in paths:
        with open(path, encoding="utf-8") as f:
            docs.append((os.path.basename(path), f.read()))
    return docs


def embed_text(text: str) -> list[float]:
    return config.get_embedder().encode(text, normalize_embeddings=True).tolist()


def build_vectordb() -> None:
    client = chromadb.PersistentClient(path=config.CHROMA_DB_DIR)
    collection = client.get_or_create_collection(name=config.COLLECTION_NAME)

    if collection.count() > 0:
        print(
            f"컬렉션 '{config.COLLECTION_NAME}'에 이미 {collection.count()}개 청크가 있습니다. "
            "임베딩을 건너뜁니다."
        )
        return

    docs = load_documents(config.DATA_DIR)
    if not docs:
        print(f"{config.DATA_DIR}에 문서가 없습니다.")
        return

    ids, texts, embeddings, metadatas = [], [], [], []

    for filename, text in docs:
        chunks = chunk_markdown(text, config.CHUNK_SIZE, config.CHUNK_OVERLAP)
        for i, chunk in enumerate(chunks):
            chunk_id = f"{filename}::{i}"
            print(f"임베딩 중: {chunk_id}")
            ids.append(chunk_id)
            texts.append(chunk.text)
            embeddings.append(embed_text(chunk.text))
            metadatas.append({"source": filename, "header": chunk.header or ""})

    collection.add(ids=ids, documents=texts, embeddings=embeddings, metadatas=metadatas)
    print(f"총 {len(ids)}개 청크를 '{config.COLLECTION_NAME}' 컬렉션에 저장했습니다.")


if __name__ == "__main__":
    build_vectordb()
