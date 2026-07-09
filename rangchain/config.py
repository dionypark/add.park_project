import os

from dotenv import load_dotenv

load_dotenv()

ANTHROPIC_API_KEY = os.environ["ANTHROPIC_API_KEY"]

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DATA_DIR = os.path.join(BASE_DIR, "data", "aws_docs")
CHROMA_DB_DIR = os.path.join(BASE_DIR, "vectordb")
COLLECTION_NAME = "aws_advisor_docs"

EMBEDDING_MODEL = "jhgan/ko-sroberta-multitask"
GENERATION_MODEL = "claude-sonnet-5"

CHUNK_SIZE = 800
CHUNK_OVERLAP = 100

TOP_K = 4

# LangSmith: LANGCHAIN_TRACING_V2=true, LANGCHAIN_API_KEY, LANGCHAIN_PROJECT는
# .env에서 로드되어 langchain/langsmith 라이브러리가 알아서 읽는다 (코드에서 직접 참조 안 함).
