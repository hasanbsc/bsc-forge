"""BSC Forge — LLM Yöneticisi (Model Sağlayıcı Soyutlama Katmanı)

Gemini, Groq ve Ollama API'lerini tek bir arayüzde birleştirir.
Streaming (akış) desteği ile token token yanıt üretir.
"""
import json
from typing import AsyncGenerator

import httpx
from google import genai
from groq import AsyncGroq

from config import settings


class LLMManager:
    """Farklı model sağlayıcılarını yöneten ana sınıf."""

    def __init__(self):
        self._gemini_client = None
        self._groq_client = None

    # ─── Gemini ────────────────────────────────────────────

    def _get_gemini_client(self):
        if self._gemini_client is None and settings.is_gemini_configured():
            self._gemini_client = genai.Client(api_key=settings.GEMINI_API_KEY)
        return self._gemini_client

    async def stream_gemini(
        self, messages: list[dict], model: str = "gemini-2.5-flash"
    ) -> AsyncGenerator[str, None]:
        """Gemini API'den streaming yanıt al."""
        client = self._get_gemini_client()
        if not client:
            yield "[HATA] Gemini API anahtarı yapılandırılmamış. .env dosyasını kontrol et."
            return

        # Mesaj geçmişini Gemini formatına dönüştür
        contents = []
        for msg in messages:
            role = "user" if msg["role"] == "user" else "model"
            contents.append(
                genai.types.Content(
                    role=role,
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
            for chunk in response:
                if chunk.text:
                    yield chunk.text
        except Exception as e:
            yield f"\n\n[HATA] Gemini yanıt veremedi: {str(e)}"

    # ─── Groq ─────────────────────────────────────────────

    def _get_groq_client(self) -> AsyncGroq | None:
        if self._groq_client is None and settings.is_groq_configured():
            self._groq_client = AsyncGroq(api_key=settings.GROQ_API_KEY)
        return self._groq_client

    async def stream_groq(
        self, messages: list[dict], model: str = "llama-3.3-70b-versatile"
    ) -> AsyncGenerator[str, None]:
        """Groq API'den streaming yanıt al."""
        client = self._get_groq_client()
        if not client:
            yield "[HATA] Groq API anahtarı yapılandırılmamış. .env dosyasını kontrol et."
            return

        # Groq OpenAI uyumlu format kullanır
        groq_messages = [
            {"role": msg["role"], "content": msg["content"]}
            for msg in messages
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
            yield f"\n\n[HATA] Groq yanıt veremedi: {str(e)}"

    # ─── Ollama (Yerel) ───────────────────────────────────

    async def stream_ollama(
        self, messages: list[dict], model: str = "qwen2.5-coder:1.5b"
    ) -> AsyncGenerator[str, None]:
        """Ollama (yerel model) üzerinden streaming yanıt al."""
        url = f"{settings.OLLAMA_BASE_URL}/api/chat"
        payload = {
            "model": model,
            "messages": [
                {"role": msg["role"], "content": msg["content"]}
                for msg in messages
            ],
            "stream": True,
        }

        try:
            async with httpx.AsyncClient(timeout=120.0) as client:
                async with client.stream("POST", url, json=payload) as response:
                    if response.status_code != 200:
                        yield f"[HATA] Ollama bağlantı hatası (HTTP {response.status_code}). Ollama çalışıyor mu?"
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
            yield "[HATA] Ollama'ya bağlanılamadı. Ollama'nın çalıştığından emin ol: `ollama serve`"
        except Exception as e:
            yield f"\n\n[HATA] Ollama hatası: {str(e)}"

    # ─── Birleşik Akış ────────────────────────────────────

    async def stream(
        self, messages: list[dict], provider: str = "gemini", model: str | None = None
    ) -> AsyncGenerator[str, None]:
        """Seçilen sağlayıcıdan streaming yanıt al.

        Otomatik fallback: Gemini başarısız olursa Groq'a geçer.
        """
        if provider == "gemini":
            gen = self.stream_gemini(messages, model or "gemini-2.5-flash")
        elif provider == "groq":
            gen = self.stream_groq(messages, model or "llama-3.3-70b-versatile")
        elif provider == "ollama":
            gen = self.stream_ollama(messages, model or "qwen2.5-coder:1.5b")
        else:
            yield f"[HATA] Bilinmeyen sağlayıcı: {provider}"
            return

        async for token in gen:
            yield token


# Tek bir global instance
llm_manager = LLMManager()
