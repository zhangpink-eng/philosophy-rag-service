import os
from pathlib import Path
from dotenv import load_dotenv

load_dotenv()

# Base paths
BASE_DIR = Path(__file__).parent.parent
DATA_DIR = BASE_DIR / "data"
MODELS_DIR = BASE_DIR / "models"

# Qdrant configuration
QDRANT_HOST = os.getenv("QDRANT_HOST", "localhost")
QDRANT_PORT = int(os.getenv("QDRANT_PORT", "6333"))
QDRANT_COLLECTION = "philosophy_documents"

# DeepSeek API configuration
DEEPSEEK_API_KEY = os.getenv("DEEPSEEK_API_KEY", "")
DEEPSEEK_BASE_URL = "https://api.deepseek.com"
DEEPSEEK_MODEL = "deepseek-chat"

# Model paths
BGE_M3_MODEL_PATH = str(MODELS_DIR / "bge-m3")
RERANKER_MODEL_PATH = str(MODELS_DIR / "bge-reranker-v2-m3")

# Chunk configuration
CHUNK_SIZE = 512
CHUNK_OVERLAP = 64

# Retrieval configuration
RETRIEVAL_TOP_K = 20
RERANK_TOP_K = 5

# Translation cache
TRANSLATION_CACHE_DIR = DATA_DIR / "translation_cache"
TRANSLATION_CACHE_DIR.mkdir(exist_ok=True)

# Raw data directory
RAW_DATA_DIR = DATA_DIR / "raw"

# Vector dimensions
DENSE_DIMENSION = 1024

# LLM configuration
LLM_TEMPERATURE = 0.7
LLM_MAX_TOKENS = 2000

# PostgreSQL configuration
POSTGRES_HOST = os.getenv("POSTGRES_HOST", "localhost")
POSTGRES_PORT = int(os.getenv("POSTGRES_PORT", "5432"))
POSTGRES_USER = os.getenv("POSTGRES_USER", "postgres")
POSTGRES_PASSWORD = os.getenv("POSTGRES_PASSWORD", "postgres")
POSTGRES_DB = os.getenv("POSTGRES_DB", "philosophy_db")

# Redis configuration
REDIS_HOST = os.getenv("REDIS_HOST", "localhost")
REDIS_PORT = int(os.getenv("REDIS_PORT", "6379"))

# JWT configuration
JWT_SECRET_KEY = os.getenv("JWT_SECRET_KEY", "your-secret-key-change-in-production")
JWT_ALGORITHM = "HS256"
JWT_EXPIRATION_HOURS = 24 * 7  # 7 days
