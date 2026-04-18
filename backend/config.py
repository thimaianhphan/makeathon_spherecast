"""Configuration for Agnes — AI Supply Chain Manager."""

from dotenv import load_dotenv
import os

load_dotenv()
GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY", "")
GEMINI_BASE_URL = "https://generativelanguage.googleapis.com/v1beta/openai/"
GEMINI_MODEL = os.environ.get("GEMINI_MODEL", "gemini-2.5-flash-lite")

HOST = "0.0.0.0"
PORT = 8000

# Database
SQLITE_DB_PATH = os.environ.get("SQLITE_DB_PATH", "data/db.sqlite")

# EU Compliance
EU_14_ALLERGENS = [
    "cereals_containing_gluten",
    "crustaceans",
    "eggs",
    "fish",
    "peanuts",
    "soybeans",
    "milk",
    "nuts",
    "celery",
    "mustard",
    "sesame",
    "sulphur_dioxide_sulphites",
    "lupin",
    "molluscs",
]
MIN_COMPLIANCE_CONFIDENCE = 0.6  # below this → "uncertain"
BLOCK_ON_UNCERTAIN_ALLERGEN = True  # conservative: block if allergen status unclear

# Thresholds
TRUST_THRESHOLD = 0.70
REGISTRY_MIN_TRUST = 0.70
MIN_ESG_SCORE = 50
BUDGET_CEILING_EUR = 500000

# Enrichment
ENABLE_EXTERNAL_ENRICHMENT = os.environ.get("ENABLE_EXTERNAL_ENRICHMENT", "true").lower() in (
    "1",
    "true",
    "yes",
)
OPENFOODFACTS_API_URL = "https://world.openfoodfacts.org/api/v2"

# Web search / retrieval
ENABLE_WEB_SEARCH = os.environ.get("ENABLE_WEB_SEARCH", "true").lower() in ("1", "true", "yes")
WEB_SEARCH_PROVIDER = os.environ.get("WEB_SEARCH_PROVIDER", "duckduckgo")  # duckduckgo | tavily | serpapi
TAVILY_API_KEY = os.environ.get("TAVILY_API_KEY", "")
HTTP_TIMEOUT_SECONDS = int(os.environ.get("HTTP_TIMEOUT_SECONDS", "8"))
EVIDENCE_CACHE_TTL_HOURS = int(os.environ.get("EVIDENCE_CACHE_TTL_HOURS", "24"))

# Label vision (optional multimodal path)
ENABLE_LABEL_VISION = os.environ.get("ENABLE_LABEL_VISION", "false").lower() in ("1", "true", "yes")

# Protocol transport
ENABLE_EXTERNAL_AGENT_TRANSPORT = os.environ.get("ENABLE_EXTERNAL_AGENT_TRANSPORT", "").lower() in (
    "1",
    "true",
    "yes",
)
AGENT_PROTOCOL_SECRET = os.environ.get("AGENT_PROTOCOL_SECRET", "")
