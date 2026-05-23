"""BSC Forge — Sohbet Router'ı

REST endpoint'leri ve WebSocket üzerinden gerçek zamanlı sohbet akışı sağlar.
"""
import json
from fastapi import APIRouter, WebSocket, WebSocketDisconnect
from pydantic import BaseModel

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


# ─── Oturum Yönetimi ──────────────────────────────────

@router.post("/sessions")
async def create_session(body: SessionCreate):
    """Yeni sohbet oturumu oluştur."""
    session_id = await chat_history.create_session(title=body.title, product=body.product)
    return {"session_id": session_id, "title": body.title}


@router.get("/sessions")
async def list_sessions(product: str | None = None):
    """Sohbet oturumlarını listele."""
    sessions = await chat_history.get_sessions(product=product)
    return {"sessions": sessions}


@router.get("/sessions/{session_id}/messages")
async def get_session_messages(session_id: str):
    """Bir oturumun mesajlarını getir."""
    messages = await chat_history.get_messages(session_id)
    return {"messages": messages}


@router.delete("/sessions/{session_id}")
async def delete_session(session_id: str):
    """Bir oturumu sil."""
    await chat_history.delete_session(session_id)
    return {"status": "silindi"}


# ─── WebSocket Sohbet Akışı ───────────────────────────

@router.websocket("/ws")
async def chat_websocket(websocket: WebSocket):
    """WebSocket üzerinden gerçek zamanlı sohbet.

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

    try:
        while True:
            # İstemciden mesaj bekle
            raw = await websocket.receive_text()
            data = json.loads(raw)

            # Frontend heartbeat
            if data.get("type") == "ping":
                await websocket.send_json({"type": "pong"})
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

                await websocket.send_json({"type": "token", "content": msg})
                if sid:
                    await chat_history.add_message(sid, "assistant", msg)
                await websocket.send_json({"type": "done", "content": ""})
                continue

            message = data.get("message", "")
            session_id = data.get("session_id")
            provider = data.get("provider", "auto")
            model = data.get("model")
            routing = data.get("routing", "auto" if provider == "auto" else "manual")
            history = data.get("history", [])
            product_id = data.get("product_id", "forge")

            # Ürün konfigürasyonunu yükle
            product_cfg = await product_store.get_product(product_id or "forge")
            product_system_prompt = product_cfg.get("system_prompt") if product_cfg else None
            product_tools = product_cfg.get("tools_enabled") if product_cfg else None

            if not message.strip():
                await websocket.send_json({"type": "error", "content": "Boş mesaj gönderilemez."})
                continue

            # Akıllı model seçimi
            decision = await model_router.route(
                message=message,
                provider=provider,
                model=model,
                routing=routing,
                history=history,
            )
            provider = decision.provider
            model = decision.model

            await websocket.send_json(model_active_event(
                provider=decision.provider,
                model=decision.model,
                label=decision.label,
            ))

            if routing == "auto" or data.get("provider") == "auto":
                await websocket.send_json({
                    "type": "routing",
                    "content": f"🎯 {decision.reason}",
                    "decision": decision.to_dict(),
                })

            # Oturuma kaydet (varsa)
            if session_id:
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
                    await websocket.send_json(event)

                input_chars = sum(len(str(m.get("content", ""))) for m in history) + len(message)
                usage = {"input": input_chars // 4, "output": len(full_response) // 4}
                await websocket.send_json({"type": "done", "content": "", "usage": usage})

                if session_id and full_response.strip():
                    await chat_history.add_message(session_id, "assistant", full_response)

                    if len(history) == 0:
                        title = message[:50] + ("..." if len(message) > 50 else "")
                        await chat_history.update_session_title(session_id, title)

            except Exception as e:
                await websocket.send_json({"type": "error", "content": f"Model hatası: {str(e)}"})

    except WebSocketDisconnect:
        pass
    except Exception:
        pass
