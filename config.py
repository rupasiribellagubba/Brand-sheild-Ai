import os
from pathlib import Path

try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:  # python-dotenv is optional
    pass

BASE_DIR = Path(__file__).resolve().parent


class Config:
    SECRET_KEY = os.getenv("SECRET_KEY", "dev-only-change-me")
    DATABASE = os.getenv("DATABASE_PATH", str(BASE_DIR / "brandshield.db"))
    MAX_CONTENT_LENGTH = 1 * 1024 * 1024  # 1 MB upload cap


# Configurable risk weights (each kind sums to 100).
RISK_WEIGHTS = {
    "social": {
        "name_similarity": 30,
        "username_similarity": 25,
        "url_lookalike": 20,
        "description_similarity": 10,
        "suspicious_wording": 15,
    },
    "app": {
        "name_similarity": 30,
        "developer_mismatch": 25,
        "app_id_similarity": 15,
        "description_similarity": 10,
        "suspicious_wording": 20,
    },
}

# Score >= medium -> Medium, >= high -> High, otherwise Low.
RISK_THRESHOLDS = {"medium": 35, "high": 65}

SUSPICIOUS_TERMS = [
    "giveaway", "free", "claim", "reward", "verify", "verification", "login",
    "urgent", "airdrop", "winner", "prize", "refund", "unlock", "bonus",
    "official support", "customer care", "helpdesk", "crypto", "investment",
]

VALID_STATUSES = ["New", "Under Review", "Confirmed Suspicious", "False Positive"]
