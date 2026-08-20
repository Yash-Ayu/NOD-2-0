"""
NOD 2.0 - Configuration
"""
import os
from dotenv import load_dotenv

load_dotenv()

class Config:
    SECRET_KEY = os.environ.get("SECRET_KEY", "nod-secret-key-change-in-production")
    JWT_SECRET = os.environ.get("JWT_SECRET", "nod-jwt-secret-change-in-production")
    BCRYPT_ROUNDS = 12
    SESSION_TIMEOUT = 900
    MAX_LOGIN_ATTEMPTS = 5
    LOCKOUT_DURATION = 300
    OLLAMA_URL = os.environ.get("OLLAMA_URL", "http://localhost:11434")
    DEFAULT_MODEL = os.environ.get("DEFAULT_MODEL", "qwen3:8b")
    BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    DATA_DIR = os.path.join(BASE_DIR, "nod_data")
    VAULT_DIR = os.path.join(DATA_DIR, "vault")
    UPLOAD_DIR = os.path.join(DATA_DIR, "uploads")
    
    @classmethod
    def ensure_dirs(cls):
        for d in [cls.DATA_DIR, cls.VAULT_DIR, cls.UPLOAD_DIR]:
            os.makedirs(d, exist_ok=True)