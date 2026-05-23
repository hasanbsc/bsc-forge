"""BSC Forge — LLM Yöneticisi (Model Sağlayıcı Soyutlama Katmanı)

Gemini → Groq → Ollama otomatik fallback zinciri.
"""
import json
from typing import AsyncGenerator

import httpx
from google import genai
from groq import AsyncGroq

from config import settings, reload_env
from services.provider_utils import (
    cascade_from,
    fallback_notice,
    friendly_provider_error,
    is_error_token,
    is_fallbackable_error,
    is_ollama_available,
    is_quota_or_rate_limit,
    model_active_event,
    model_for_provider,
    GROQ_FALLBACK_MODEL,
    OLLAMA_FALLBACK_MODEL,
    DEEPSEEK_FALLBACK_MODEL,
)


class LLMManager:
    """Farklı model sağlayıcılarını yöneten ana sınıf."""

    def __init__(self):
        self._gemini_client = None
        self._groq_client = None

    def _get_gemini_client(self):
        if not settings.is_gemini_configured():
            self._gemini_client = None
            return None
        if self._gemini_client is None:
            self._gemini_client = genai.Client(api_key=settings.GEMINI_API_KEY)
        return self._gemini_client

    def _reset_clients(self):
        self._gemini_client = None
        self._groq_client = None

    def _get_groq_client(self) -> AsyncGroq | None:
        if self._groq_client is None and settings.is_groq_configured():
            self._groq_client = AsyncGroq(api_key=settings.GROQ_API_KEY)
        return self._groq_client

    async def stream_gemini(
        self, messages: list[dict], model: str = "gemini-2.5-flash"
    ) -> AsyncGenerator[str, None]:
        client = self._get_gemini_client()
        if not client:
            yield "[HATA] Gemini API anahtarı yapılandırılmamış."
            return

        contents = []
        for msg in messages:
            if msg["role"] == "system":
                gemini_role = "user"
            elif msg["role"] == "user":
                gemini_role = "user"
            else:
                gemini_role = "model"
            contents.append(
                genai.types.Content(
                    role=gemini_role,
                    parts=[genai.types.Part(text=msg["content"])],
                )
            )

        try:
            response = client.models.generate_content_stream(
                model=model,
                contents=contents,
                config=genai.types.GenerateContentConfig(
                    temperature=0.7,
                    max_output_tokens=4096,
                ),
            )
            accumulated = ""
            for chunk in response:
                if not chunk.text:
                    continue
                text = chunk.text
                if text.startswith(accumulated):
                    delta = text[len(accumulated) :]
                    accumulated = text
                else:
                    delta = text
                    accumulated += text
                if delta:
                    yield delta
        except Exception as e:
            yield f"[HATA] {friendly_provider_error(e, 'Gemini')}"

    async def stream_groq(
        self, messages: list[dict], model: str = GROQ_FALLBACK_MODEL
    ) -> AsyncGenerator[str, None]:
        client = self._get_groq_client()
        if not client:
            yield "[HATA] Groq API anahtarı yapılandırılmamış."
            return

        groq_messages = [
            {"role": msg["role"], "content": msg["content"]}
            for msg in messages
            if msg["role"] in ("system", "user", "assistant")
        ]

        try:
            stream = await client.chat.completions.create(
                model=model,
                messages=groq_messages,
                temperature=0.7,
                max_tokens=4096,
                stream=True,
            )
            async for chunk in stream:
                delta = chunk.choices[0].delta
                if delta.content:
                    yield delta.content
        except Exception as e:
            yield f"[HATA] {friendly_provider_error(e, 'Groq')}"

    async def stream_ollama(
        self, messages: list[dict], model: str = OLLAMA_FALLBACK_MODEL
    ) -> AsyncGenerator[str, None]:
        if not await is_ollama_available():
            yield (
                "[HATA] Ollama'ya bağlanılamadı. Terminalde `ollama serve` çalıştır "
                f"ve `ollama pull {model}` ile modeli indir."
            )
            return

        url = f"{settings.OLLAMA_BASE_URL.rstrip('/')}/api/chat"
        payload = {
            "model": model,
            "messages": [
                {"role": msg["role"], "content": msg["content"]}
                for msg in messages
                if msg["role"] in ("system", "user", "assistant")
            ],
            "stream": True,
        }

        try:
            async with httpx.AsyncClient(timeout=180.0) as client:
                async with client.stream("POST", url, json=payload) as response:
                    if response.status_code != 200:
                        body = await response.aread()
                        yield (
                            f"[HATA] Ollama HTTP {response.status_code}. "
                            f"Model yüklü mü? `ollama pull {model}`"
                        )
                        return
                    async for line in response.aiter_lines():
                        if line:
                            data = json.loads(line)
                            content = data.get("message", {}).get("content", "")
                            if content:
                                yield content
                            if data.get("done"):
                                break
        except httpx.ConnectError:
            yield "[HATA] Ollama'ya bağlanılamadı. `ollama serve` çalışıyor mu?"
        except Exception as e:
            yield f"[HATA] {friendly_provider_error(e, 'Ollama')}"

    async def stream_deepseek(
        self, messages: list[dict], model: str = DEEPSEEK_FALLBACK_MODEL
    ) -> AsyncGenerator[str, None]:
        if not settings.is_deepseek_configured():
            yield "[HATA] Deepseek API anahtarı yapılandırılmamış."
            return

        url = "https://api.deepseek.com/v1/chat/completions"
        headers = {
            "Authorization": f"Bearer {settings.DEEPSEEK_API_KEY}",
            "Content-Type": "application/json",
        }
        prompt = "\n".join(
            f"{m['role']}: {m['content']}" for m in messages if m['role'] in ("system", "user", "assistant")
        )
        payload = {"model": model, "prompt": prompt, "max_tokens": 4096, "temperature": 0.7}

        try:
            async with httpx.AsyncClient(timeout=120.0) as client:
                r = await client.post(url, json=payload, headers=headers)
                if r.status_code != 200:
                    yield f"[HATA] Deepseek HTTP {r.status_code}: {r.text[:400]}"
                    return
                data = r.json()
                # Common fields: 'text', 'output', or choices[0].text
                text = None
                if isinstance(data, dict):
                    text = data.get("text") or data.get("output")
                    if not text and data.get("choices"):
                        ch = data.get("choices")
                        if isinstance(ch, list) and ch:
                            text = ch[0].get("text") or ch[0].get("message", {}).get("content")
                if text:
                    yield text
                    return
                yield "[HATA] Deepseek: beklenmeyen cevap formatı."
        except Exception as e:
            yield f"[HATA] {friendly_provider_error(e, 'Deepseek')}"

    async def _stream_single(
        self, provider: str, messages: list[dict], model: str
    ) -> AsyncGenerator[str, None]:
        if provider == "gemini":
            async for t in self.stream_gemini(messages, model):
                yield t
        elif provider == "groq":
            async for t in self.stream_groq(messages, model):
                yield t
        elif provider == "ollama":
            async for t in self.stream_ollama(messages, model):
                yield t
        elif provider == "deepseek":
            async for t in self.stream_deepseek(messages, model):
                yield t
        else:
            yield f"[HATA] Bilinmeyen sağlayıcı: {provider}"

    async def stream(
        self, messages: list[dict], provider: str = "gemini", model: str | None = None
    ) -> AsyncGenerator[str, None]:
        """Seçilen sağlayıcıdan stream; kota/limit → Groq → Ollama."""
        reload_env()
        self._reset_clients()

        chain = cascade_from(provider)
        last_error = ""

        for i, prov in enumerate(chain):
            prov_model = model_for_provider(prov, model if prov == provider else None)
            if prov == "ollama" and not await is_ollama_available():
                last_error = "Ollama çalışmıyor"
                continue

            if i > 0:
                yield f"\n\n{fallback_notice(chain[i - 1], prov)}\n\n"

            failed = False
            async for token in self._stream_single(prov, messages, prov_model):
                if is_error_token(token) and (
                    is_quota_or_rate_limit(token) or is_fallbackable_error(token)
                ):
                    last_error = token
                    failed = True
                    break
                yield token

            if not failed:
                return

        yield f"\n\n[HATA] Tüm sağlayıcılar denendi. Son hata: {last_error[:500]}"

    async def stream_with_notices(
        self, messages: list[dict], provider: str = "gemini", model: str | None = None
    ) -> AsyncGenerator[dict, None]:
        """Token + fallback_notice olayları (WebSocket için)."""
        reload_env()
        self._reset_clients()

        chain = cascade_from(provider)
        last_error = ""

        for i, prov in enumerate(chain):
            prov_model = model_for_provider(prov, model if prov == provider else None)
            if prov == "ollama" and not await is_ollama_available():
                last_error = "Ollama çalışmıyor"
                continue

            if i > 0:
                yield {
                    "type": "fallback",
                    "content": fallback_notice(chain[i - 1], prov),
                }
                yield model_active_event(prov, prov_model)

            failed = False
            async for token in self._stream_single(prov, messages, prov_model):
                if is_error_token(token) and (
                    is_quota_or_rate_limit(token) or is_fallbackable_error(token)
                ):
                    last_error = token
                    failed = True
                    break
                yield {"type": "token", "content": token}

            if not failed:
                return

        yield {
            "type": "error",
            "content": f"Tüm modeller denendi. {last_error[:400]}",
        }


llm_manager = LLMManager()
