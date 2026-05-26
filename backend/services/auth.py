"""BSC Forge — Üyelik & Auth servisi

- Şifre hash (bcrypt)
- JWT token üretimi ve doğrulama (HS256)
- Kullanıcı CRUD (SQLite, aiosqlite)
- FastAPI Depends için optional/required user çözücüleri

E-posta + şifre tabanlı basit auth. Anonim oturumlar `browser_id` ile
işaretlenir; üye olunca `claim_anonymous_sessions` ile hesaba bağlanır.
"""
from __future__ import annotations

import logging
import uuid
from datetime import datetime, timedelta, timezone
from typing import Optional

import aiosqlite
import bcrypt
import jwt
from email_validator import EmailNotValidError, validate_email
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from config import settings

logger = logging.getLogger("bsc_forge.auth")

# Bearer şeması — auto_error=False ile anonim isteklere izin verir.
_bearer_optional = HTTPBearer(auto_error=False)
_bearer_required = HTTPBearer(auto_error=True)


# ---------- Şifre yardımcıları ----------

def hash_password(password: str) -> str:
    return bcrypt.hashpw(password.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")


def verify_password(password: str, hashed: str) -> bool:
    try:
        return bcrypt.checkpw(password.encode("utf-8"), hashed.encode("utf-8"))
    except ValueError:
        return False


# ---------- Token yardımcıları ----------

def create_token(user_id: str) -> str:
    now = datetime.now(timezone.utc)
    payload = {
        "sub": user_id,
        "iat": int(now.timestamp()),
        "exp": int((now + timedelta(days=settings.JWT_EXPIRES_DAYS)).timestamp()),
    }
    return jwt.encode(payload, settings.JWT_SECRET, algorithm=settings.JWT_ALGORITHM)


def decode_token(token: str) -> Optional[str]:
    """Token geçerliyse user_id döner, değilse None."""
    try:
        payload = jwt.decode(token, settings.JWT_SECRET, algorithms=[settings.JWT_ALGORITHM])
        return payload.get("sub")
    except jwt.PyJWTError:
        return None


# ---------- E-posta doğrulama ----------

def normalize_email(raw: str) -> str:
    """E-postayı normalize et. Geçersizse ValueError."""
    info = validate_email(raw, check_deliverability=False)
    return info.normalized.lower()


# ---------- Kullanıcı deposu ----------

class UserStore:
    """SQLite tabanlı kullanıcı deposu."""

    def __init__(self) -> None:
        self.db_path = settings.DB_PATH

    async def init_table(self) -> None:
        async with aiosqlite.connect(self.db_path) as db:
            await db.execute(
                """
                CREATE TABLE IF NOT EXISTS users (
                    id TEXT PRIMARY KEY,
                    email TEXT NOT NULL UNIQUE,
                    password_hash TEXT NOT NULL,
                    created_at TEXT NOT NULL
                )
                """
            )
            await db.commit()

    async def create(self, email: str, password: str) -> dict:
        user_id = str(uuid.uuid4())
        now = datetime.now(timezone.utc).isoformat()
        hashed = hash_password(password)
        async with aiosqlite.connect(self.db_path) as db:
            try:
                await db.execute(
                    "INSERT INTO users (id, email, password_hash, created_at) VALUES (?, ?, ?, ?)",
                    (user_id, email, hashed, now),
                )
                await db.commit()
            except aiosqlite.IntegrityError as e:
                raise ValueError("Bu e-posta zaten kayıtlı.") from e
        return {"id": user_id, "email": email, "created_at": now}

    async def get_by_email(self, email: str) -> Optional[dict]:
        async with aiosqlite.connect(self.db_path) as db:
            db.row_factory = aiosqlite.Row
            cursor = await db.execute(
                "SELECT id, email, password_hash, created_at FROM users WHERE email = ?",
                (email,),
            )
            row = await cursor.fetchone()
            return dict(row) if row else None

    async def get_by_id(self, user_id: str) -> Optional[dict]:
        async with aiosqlite.connect(self.db_path) as db:
            db.row_factory = aiosqlite.Row
            cursor = await db.execute(
                "SELECT id, email, created_at FROM users WHERE id = ?",
                (user_id,),
            )
            row = await cursor.fetchone()
            return dict(row) if row else None


user_store = UserStore()


# ---------- FastAPI Depends ----------

async def get_current_user_optional(
    creds: Optional[HTTPAuthorizationCredentials] = Depends(_bearer_optional),
) -> Optional[dict]:
    """Bearer token varsa kullanıcıyı döner, yoksa None (anonim)."""
    if creds is None:
        return None
    user_id = decode_token(creds.credentials)
    if not user_id:
        return None
    return await user_store.get_by_id(user_id)


async def get_current_user_required(
    creds: HTTPAuthorizationCredentials = Depends(_bearer_required),
) -> dict:
    user_id = decode_token(creds.credentials)
    if not user_id:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Geçersiz veya süresi dolmuş token.",
            headers={"WWW-Authenticate": "Bearer"},
        )
    user = await user_store.get_by_id(user_id)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Kullanıcı bulunamadı.",
        )
    return user


def user_id_from_token(token: Optional[str]) -> Optional[str]:
    """WebSocket query string için: token'dan user_id çöz, geçersizse None."""
    if not token:
        return None
    return decode_token(token)
