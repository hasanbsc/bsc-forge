"""BSC Forge — Sohbet Router'ı

REST endpoint'leri ve WebSocket üzerinden gerçek zamanlı sohbet akışı sağlar.
"""
import json
import logging
from typing import Optional

from fastapi import APIRouter, Depends, Header, HTTPException, WebSocket, WebSocketDisconnect
from pydantic import BaseModel

logger = logging.getLogger("bsc_forge.chat")


async def _safe_send_json(websocket: WebSocket, payload: dict) -> bool:
    """WebSocket kopmuş olabilir; gönderim hatasını yutup False döner."""
    try:
        await websocket.send_json(payload)
        return True
    except Exception:
        # Bağlantı kapanmışsa daha fazla göndermenin anlamı yok.
        return False

from services.auth import get_current_user_optional, user_id_from_token
from services.chat_history import chat_history
from services.forge_agent import forge_agent
from services.model_router import model_router
from services.product_store import product_store
from services.provider_utils import model_active_event

router = APIRouter()


class ChatRequest(BaseModel):
    """Sohbet isteği modeli."""
    message: str
    session_id: str | None = None
    provider: str = "gemini"
    model: str | None = None
    history: list[dict] = []


class SessionCreate(BaseModel):
    """Yeni oturum oluşturma modeli."""
    title: str = "Yeni Sohbet"
    product: str = "forge"


async def _ws_can_use_session(
    session_id: str, user_id: Optional[str], browser_id: Optional[str]
) -> bool:
    """WebSocket bağlamında bir oturum sahipliğini doğrula."""
    if not session_id:
        return False
    session = await chat_history.get_session(session_id)
    if not session:
        return False
    sess_user = session.get("user_id")
    sess_browser = session.get("browser_id")
    if user_id is not None:
        return sess_user == user_id
    if sess_user is not None:
        return False
    if sess_browser is None:
        return True  # legacy
    return sess_browser == browser_id


def _can_access(session: dict, user: Optional[dict], browser_id: Optional[str]) -> bool:
    """Bir oturuma erişim yetkisi var mı?

    - Üye: yalnızca kendi user_id'sine ait sohbetler
    - Anonim: user_id NULL olan ve browser_id eşleşen sohbetler
    - Geriye dönük: hem user_id hem browser_id NULL ise (eski sohbetler) anonim
      kullanıcı erişebilir
    """
    sess_user = session.get("user_id")
    sess_browser = session.get("browser_id")
    if user is not None:
        return sess_user == user["id"]
    # Anonim
    if sess_user is not None:
        return False
    if sess_browser is None:
        return True  # legacy
    return sess_browser == browser_id


# ─── Oturum Yönetimi ──────────────────────────────────

@router.post("/sessions")
async def create_session(
    body: SessionCreate,
    user: Optional[dict] = Depends(get_current_user_optional),
    x_browser_id: Optional[str] = Header(default=None, alias="X-Browser-Id"),
):
    """Yeni sohbet oturumu oluştur."""
    user_id = user["id"] if user else None
    # Üye girişliyse browser_id'yi yine de kayda almak gerekmiyor (sahiplik user'da).
    browser_id = None if user else x_browser_id
    session_id = await chat_history.create_session(
        title=body.title,
        product=body.product,
        user_id=user_id,
        browser_id=browser_id,
    )
    return {"session_id": session_id, "title": body.title}


@router.get("/sessions")
async def list_sessions(
    product: str | None = None,
    user: Optional[dict] = Depends(get_current_user_optional),
    x_browser_id: Optional[str] = Header(default=None, alias="X-Browser-Id"),
):
    """Sohbet oturumlarını listele."""
    user_id = user["id"] if user else None
    browser_id = None if user else x_browser_id
    sessions = await chat_history.get_sessions(
        product=product, user_id=user_id, browser_id=browser_id
    )
    return {"sessions": sessions}


@router.get("/sessions/{session_id}/messages")
async def get_session_messages(
    session_id: str,
    user: Optional[dict] = Depends(get_current_user_optional),
    x_browser_id: Optional[str] = Header(default=None, alias="X-Browser-Id"),
):
    """Bir oturumun mesajlarını getir."""
    session = await chat_history.get_session(session_id)
    if not session:
        raise HTTPException(status_code=404, detail="Oturum bulunamadı.")
    if not _can_access(session, user, x_browser_id):
        raise HTTPException(status_code=403, detail="Bu oturuma erişim yetkin yok.")
    messages = await chat_history.get_messages(session_id)
    return {"messages": messages}


@router.delete("/sessions/{session_id}")
async def delete_session(
    session_id: str,
    user: Optional[dict] = Depends(get_current_user_optional),
    x_browser_id: Optional[str] = Header(default=None, alias="X-Browser-Id"),
):
    """Bir oturumu sil."""
    session = await chat_history.get_session(session_id)
    if not session:
        # Idempotent: zaten yoksa başarılı say
        return {"status": "silindi"}
    if not _can_access(session, user, x_browser_id):
        raise HTTPException(status_code=403, detail="Bu oturumu silme yetkin yok.")
    await chat_history.delete_session(session_id)
    return {"status": "silindi"}


# ─── WebSocket Sohbet Akışı ───────────────────────────

@router.websocket("/ws")
async def chat_websocket(websocket: WebSocket):
    """WebSocket üzerinden gerçek zamanlı sohbet.

    Bağlantı query string'i opsiyonel:
        ?token=<JWT>&browser_id=<uuid>

    İstemci JSON gönderir:
    {
        "message": "Merhaba!",
        "session_id": "abc-123",       (opsiyonel)
        "provider": "gemini",          (gemini|groq|ollama)
        "model": "gemini-2.5-flash",   (opsiyonel)
        "history": [...]               (önceki mesajlar)
    }

    Sunucu streaming yanıt gönderir:
    {"type": "token", "content": "Mer"}
    {"type": "token", "content": "haba"}
    {"type": "done",  "content": ""}
    {"type": "error", "content": "..."}
    """
    await websocket.accept()

    qp = websocket.query_params
    conn_user_id = user_id_from_token(qp.get("token"))
    conn_browser_id = qp.get("browser_id") if not conn_user_id else None

    try:
        while True:
            # İstemciden mesaj bekle
            raw = await websocket.receive_text()
            try:
                data = json.loads(raw)
            except json.JSONDecodeError:
                await _safe_send_json(websocket, {
                    "type": "error",
                    "content": "Geçersiz JSON. Mesaj işlenemedi.",
                })
                continue

            # Frontend heartbeat
            if data.get("type") == "ping":
                await _safe_send_json(websocket, {"type": "pong"})
                continue

            # Kullanıcı dosya yazma onayı verdi / reddetti
            if data.get("type") == "approval_response":
                approved = data.get("approved", False)
                file_path = data.get("path", "")
                folder = data.get("folder", "")
                sid = data.get("session_id")

                if not approved:
                    msg = "❌ Dosya oluşturma iptal edildi."
                else:
                    target = f"`{folder}/{file_path}`" if folder else f"`{file_path}`"
                    msg = f"✅ {target} bilgisayara kaydedildi."

                await _safe_send_json(websocket, {"type": "token", "content": msg})
                if sid and await _ws_can_use_session(sid, conn_user_id, conn_browser_id):
                    await chat_history.add_message(sid, "assistant", msg)
                # "done" event'i göndermiyoruz — agent.run kendisi yayıyor zaten
                # ve birden fazla "done" frontend'in queue mantığını karıştırır
                continue

            message = data.get("message", "")
            session_id = data.get("session_id")
            provider = data.get("provider", "auto")
            model = data.get("model")
            routing = data.get("routing", "auto" if provider == "auto" else "manual")
            history = data.get("history", [])
            product_id = data.get("product_id", "forge")
            # Opsiyonel: yerel orchestrator (Mistral 7B) ile ön-analiz (UI toggle)
            use_orchestrator = bool(data.get("orchestrate", False))

            # Ürün konfigürasyonunu yükle
            product_cfg = await product_store.get_product(product_id or "forge")
            product_system_prompt = product_cfg.get("system_prompt") if product_cfg else None
            product_tools = product_cfg.get("tools_enabled") if product_cfg else None

            if not message.strip():
                await _safe_send_json(websocket, {"type": "error", "content": "Boş mesaj gönderilemez."})
                continue

            # Akıllı model seçimi
            decision = await model_router.route(
                message=message,
                provider=provider,
                model=model,
                routing=routing,
                history=history,
                use_orchestrator=use_orchestrator,
            )
            provider = decision.provider
            model = decision.model

            await _safe_send_json(websocket, model_active_event(
                provider=decision.provider,
                model=decision.model,
                label=decision.label,
            ))

            if routing == "auto" or data.get("provider") == "auto":
                await _safe_send_json(websocket, {
                    "type": "routing",
                    "content": f"🎯 {decision.reason}",
                    "decision": decision.to_dict(),
                })

            # Oturum sahipliği kontrolü; uymuyorsa kaydı atla (sohbet yine de akar)
            session_ok = bool(session_id) and await _ws_can_use_session(
                session_id, conn_user_id, conn_browser_id
            )
            if session_id and not session_ok:
                logger.warning(
                    "WS oturum yetki reddi: session=%s user=%s browser=%s",
                    session_id, conn_user_id, conn_browser_id,
                )

            if session_ok:
                await chat_history.add_message(session_id, "user", message)

            # Forge Ajan: araçlar + streaming yanıt
            full_response = ""
            try:
                async for event in forge_agent.run(
                    user_message=message,
                    history=history,
                    provider=provider,
                    model=model,
                    system_prompt=product_system_prompt,
                    tools_enabled=product_tools,
                ):
                    if event["type"] == "token":
                        full_response += event["content"]
                    if not await _safe_send_json(websocket, event):
                        # Bağlantı koptu — ajan döngüsünü iptal et
                        logger.info("WebSocket koptu; ajan akışı iptal edildi.")
                        return

                input_chars = sum(len(str(m.get("content", ""))) for m in history) + len(message)
                usage = {"input": input_chars // 4, "output": len(full_response) // 4}
                await _safe_send_json(websocket, {"type": "done", "content": "", "usage": usage})

                if session_ok and full_response.strip():
                    await chat_history.add_message(session_id, "assistant", full_response)

                    if len(history) == 0:
                        title = message[:50] + ("..." if len(message) > 50 else "")
                        await chat_history.update_session_title(session_id, title)

            except Exception as e:
                # Ajan döngüsünde beklenmedik hata: kullanıcıya bildir ve döngüyü açık tut.
                logger.exception("Ajan hatası: %s", e)
                await _safe_send_json(websocket, {
                    "type": "error",
                    "content": f"Model hatası: {str(e)[:300]}",
                })

    except WebSocketDisconnect:
        # Normal kapanış — log gerekmez.
        return
    except Exception as e:
        # Beklenmedik üst seviye hata: logla, kullanıcıya gönderebilirsek gönder.
        logger.exception("WebSocket beklenmedik hata: %s", e)
        await _safe_send_json(websocket, {
            "type": "error",
            "content": "Sunucuda beklenmedik bir hata oluştu; bağlantı yeniden kurulacak.",
        })
