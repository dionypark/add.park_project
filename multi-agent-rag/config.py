import os

from dotenv import load_dotenv

load_dotenv()

ANTHROPIC_API_KEY = os.environ["ANTHROPIC_API_KEY"]

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DATA_DIR = os.path.join(BASE_DIR, "data", "aws_docs")
CHROMA_DB_DIR = os.path.join(BASE_DIR, "vectordb")
COLLECTION_NAME = "aws_advisor_docs"

EMBEDDING_MODEL = "jhgan/ko-sroberta-multitask"

# 에이전트마다 다른 모델을 쓸 수도 있지만, 이번 버전은 모델은 하나로 고정.
GENERATION_MODEL = "claude-sonnet-5"

CHUNK_SIZE = 800
CHUNK_OVERLAP = 100

TOP_K = 4
