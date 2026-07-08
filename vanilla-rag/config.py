import os

import anthropic
from dotenv import load_dotenv

load_dotenv()

GOOGLE_API_KEY = os.environ["GOOGLE_API_KEY"]  # RAGAS judge(LLM/임베딩)용으로 계속 사용
ANTHROPIC_API_KEY = os.environ["ANTHROPIC_API_KEY"]

anthropic_client = anthropic.Anthropic(api_key=ANTHROPIC_API_KEY)

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DATA_DIR = os.path.join(BASE_DIR, "data", "aws_docs")
CHROMA_DB_DIR = os.path.join(BASE_DIR, "vectordb")
COLLECTION_NAME = "aws_advisor_docs"

EMBEDDING_MODEL = "jhgan/ko-sroberta-multitask"
GENERATION_MODEL = "claude-sonnet-5"

CHUNK_SIZE = 800
CHUNK_OVERLAP = 100

TOP_K = 4

_embedder = None


def get_embedder():
    global _embedder
    if _embedder is None:
        from sentence_transformers import SentenceTransformer
        _embedder = SentenceTransformer(EMBEDDING_MODEL)
    return _embedder
