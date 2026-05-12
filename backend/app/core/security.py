import os
from datetime import datetime, timedelta, timezone
from typing import Any

from cryptography.fernet import Fernet
from jose import JWTError, jwt
from passlib.context import CryptContext

SECRET_KEY = os.environ["JWT_SECRET_KEY"]
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 60 * 24  # 24 hours

_fernet_key = os.environ["FERNET_KEY"]
_fernet = Fernet(_fernet_key.encode())

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")


# --- Passwords ---

def hash_password(password: str) -> str:
    return pwd_context.hash(password)


def verify_password(plain: str, hashed: str) -> bool:
    return pwd_context.verify(plain, hashed)


# --- JWT ---

def create_access_token(subject: str, tenant_id: str, role: str) -> str:
    expire = datetime.now(timezone.utc) + timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    payload = {
        "sub": subject,
        "tenant_id": tenant_id,
        "role": role,
        "exp": expire,
    }
    return jwt.encode(payload, SECRET_KEY, algorithm=ALGORITHM)


def decode_access_token(token: str) -> dict[str, Any]:
    try:
        return jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
    except JWTError:
        raise ValueError("Invalid or expired token")


# --- Credential encryption (for data source configs) ---

def encrypt_config(config: str) -> str:
    """Encrypt a JSON string of connector credentials."""
    return _fernet.encrypt(config.encode()).decode()


def decrypt_config(encrypted: str) -> str:
    """Decrypt a connector credentials blob back to a JSON string."""
    return _fernet.decrypt(encrypted.encode()).decode()


# --- Key generation helper (run once to create .env values) ---

def generate_keys() -> dict[str, str]:
    return {
        "JWT_SECRET_KEY": os.urandom(32).hex(),
        "FERNET_KEY": Fernet.generate_key().decode(),
    }
