"""AWS 문서를 청킹하여 LangChain Document로 감싸고, HuggingFace 임베딩으로 Chroma에 영구 저장한다.

이미 컬렉션에 데이터가 있고 원본 문서가 안 바뀌었으면 재임베딩을 건너뛴다.
문서가 바뀌었으면(fingerprint 불일치) 컬렉션을 지우고 다시 인덱싱한다.
"""
from __future__ import annotations

import glob
import hashlib
import os

from langchain_chroma import Chroma
from langchain_core.documents import Document
from langchain_huggingface import HuggingFaceEmbeddings

import config
from chunking import chunk_markdown

FINGERPRINT_PATH = os.path.join(config.CHROMA_DB_DIR, "fingerprint.txt")


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


def _fingerprint(docs: list[tuple[str, str]]) -> str:
    """원본 문서들의 내용을 해시로 요약한다. 이 값이 바뀌면 문서가 바뀐 것."""
    h = hashlib.sha256()
    for filename, text in docs:
        h.update(filename.encode())
        h.update(text.encode())
    return h.hexdigest()


def _read_fingerprint() -> str | None:
    if os.path.exists(FINGERPRINT_PATH):
        with open(FINGERPRINT_PATH) as f:
            return f.read().strip()
    return None


def _write_fingerprint(fingerprint: str) -> None:
    os.makedirs(config.CHROMA_DB_DIR, exist_ok=True)
    with open(FINGERPRINT_PATH, "w") as f:
        f.write(fingerprint)


def build_embeddings() -> HuggingFaceEmbeddings:
    return HuggingFaceEmbeddings(model_name=config.EMBEDDING_MODEL)


def _make_vectorstore(embeddings: HuggingFaceEmbeddings) -> Chroma:
    return Chroma(
        collection_name=config.COLLECTION_NAME,
        embedding_function=embeddings,
        persist_directory=config.CHROMA_DB_DIR,
    )


def build_vectordb() -> Chroma:
    embeddings = build_embeddings()
    vectorstore = _make_vectorstore(embeddings)

    docs = load_documents(config.DATA_DIR)
    fingerprint = _fingerprint(docs)
    already_indexed = len(vectorstore.get(limit=1)["ids"]) > 0

    if already_indexed and _read_fingerprint() == fingerprint:
        print(f"컬렉션 '{config.COLLECTION_NAME}'이 최신 상태입니다. 임베딩을 건너뜁니다.")
        return vectorstore

    if already_indexed:
        print("원본 문서가 바뀐 것을 감지했습니다. 컬렉션을 비우고 다시 인덱싱합니다.")
        vectorstore.delete_collection()
        vectorstore = _make_vectorstore(embeddings)

    if not docs:
        print(f"{config.DATA_DIR}에 문서가 없습니다.")
        return vectorstore

    documents = []
    for filename, text in docs:
        chunks = chunk_markdown(text, config.CHUNK_SIZE, config.CHUNK_OVERLAP)
        for i, chunk in enumerate(chunks):
            documents.append(
                Document(
                    page_content=chunk.text,
                    metadata={"source": filename, "header": chunk.header or "", "chunk_id": f"{filename}::{i}"},
                )
            )

    vectorstore.add_documents(documents)
    _write_fingerprint(fingerprint)
    print(f"총 {len(documents)}개 청크를 '{config.COLLECTION_NAME}' 컬렉션에 저장했습니다.")
    return vectorstore


if __name__ == "__main__":
    build_vectordb()
