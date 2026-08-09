import os

import torch
from dotenv import load_dotenv

load_dotenv()

# t3.small(vCPU 2개) 배포 기준 - 임베딩 모델(HuggingFaceEmbeddings)이 기본값으로 CPU 코어 수만큼
# 쓰레드를 잡으려 해서, vCPU 수에 맞춰 제한 안 하면 다른 프로세스(FastAPI/Streamlit)와 CPU를 놓고
# 경합해 오히려 느려질 수 있다.
torch.set_num_threads(2)

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

# 문서가 25개(청크 700개+)로 늘어난 뒤로는 4개는 너무 적어서, 여러 주제가 섞인 질문(예:
# "Spring Boot+PostgreSQL 구성 추천")에서 일부 관련 청크를 놓치는 경우가 있었다. 6으로 늘림.
TOP_K = 6
