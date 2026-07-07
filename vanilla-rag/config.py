import os

from dotenv import load_dotenv
from google import genai

load_dotenv()

GOOGLE_API_KEY = os.environ["GOOGLE_API_KEY"]

client = genai.Client(api_key=GOOGLE_API_KEY)

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DATA_DIR = os.path.join(BASE_DIR, "data", "aws_docs")
CHROMA_DB_DIR = os.path.join(BASE_DIR, "vectordb")
COLLECTION_NAME = "aws_advisor_docs"

EMBEDDING_MODEL = "text-embedding-004"
GENERATION_MODEL = "gemini-2.5-flash"

CHUNK_SIZE = 800
CHUNK_OVERLAP = 100

TOP_K = 4
