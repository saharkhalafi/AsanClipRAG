APP_NAME = "AsanClip RAG"
VERSION = "1.0.0"
import os

# Cache
CACHE_TTL_SEARCH = 3600
CACHE_TTL_EMBEDDING = 86400

# Search Limits
MAX_QUERY_LENGTH = 500
DEFAULT_TOP_K = 5          # products shown to end users
USER_RESPONSE_TOP_K = 5
USER_CAPTION_LIMIT = 5
INTERNAL_RANK_TOP_K = 20   # rank deeper internally; eval may request via top_k
RESPONSE_TOP_K = USER_RESPONSE_TOP_K
CANDIDATE_POOL_LIMIT = 200

# Embeddings / FAISS
EMBEDDING_DIMENSION = int(os.getenv("EMBEDDING_DIMENSION", "3072"))
FAISS_INDEX_PATH = os.getenv("FAISS_INDEX_PATH", "indexes/faiss.index")
METADATA_CACHE_TTL_SECONDS = int(os.getenv("METADATA_CACHE_TTL_SECONDS", "300"))

# Rate Limiting
DEFAULT_RATE_LIMIT = "100/minute"
EMBEDDING_RATE_LIMIT = "30/minute"

# Occasions
OCCASION_CATEGORIES = [
    "تولد",
    "سالگرد_ازدواج",
    "عقد_عروسی",
    "ولنتاین",
    "نوروز",
    "کریسمس",
    "یلدا",
    "روز پدر",
    "روز مادر",
    "روز معلم",
    "روز مهندس",
    "پیام تسلیت",
    "تخفیف",
    "بلک فرایدی",
    "محصول جدید",
    "افتتاحیه",
    "دعوت"
]
