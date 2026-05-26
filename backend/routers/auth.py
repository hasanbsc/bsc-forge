"""BSC Forge — Üyelik (Auth) Router'ı

E-posta + şifre tabanlı basit auth. Token: JWT (Bearer).
Anonim sohbetler `browser_id` ile bağlanır; üye olunca claim-anonymous ile
hesaba taşınır.
"""
import logging

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field

from services.auth import (
    create_token,
    get_current_user_required,
    normalize_email,
    user_store,
    verify_password,
)
from services.chat_history import chat_history

logger = logging.getLogger("bsc_forge.auth_router")

router = APIRouter()


class RegisterRequest(BaseModel):
    email: str
    password: str = Field(min_length=8, max_length=128)


class LoginRequest(BaseModel):
    email: str
    password: str


class ClaimAnonymousRequest(BaseModel):
    browser_id: str = Field(min_length=1, max_length=128)


def _user_public(user: dict) -> dict:
    return {"id": user["id"], "email": user["email"], "created_at": user["created_at"]}


@router.post("/register", status_code=status.HTTP_201_CREATED)
async def register(body: RegisterRequest):
    try:
        email = normalize_email(body.email)
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Geçersiz e-posta: {e}")

    try:
        user = await user_store.create(email=email, password=body.password)
    except ValueError as e:
        raise HTTPException(status_code=409, detail=str(e))

    token = create_token(user["id"])
    return {"token": token, "user": _user_public(user)}


@router.post("/login")
async def login(body: LoginRequest):
    try:
        email = normalize_email(body.email)
    except Exception:
        raise HTTPException(status_code=401, detail="E-posta veya şifre hatalı.")

    user = await user_store.get_by_email(email)
    if not user or not verify_password(body.password, user["password_hash"]):
        raise HTTPException(status_code=401, detail="E-posta veya şifre hatalı.")

    token = create_token(user["id"])
    return {"token": token, "user": _user_public(user)}


@router.get("/me")
async def me(user: dict = Depends(get_current_user_required)):
    return {"user": _user_public(user)}


@router.post("/claim-anonymous")
async def claim_anonymous(
    body: ClaimAnonymousRequest,
    user: dict = Depends(get_current_user_required),
):
    """Bu browser_id ile başlatılmış anonim sohbetleri kullanıcıya bağla."""
    claimed = await chat_history.claim_anonymous_sessions(
        user_id=user["id"], browser_id=body.browser_id
    )
    logger.info("claim-anonymous: user=%s browser=%s adet=%d", user["id"], body.browser_id, claimed)
    return {"claimed": claimed}
