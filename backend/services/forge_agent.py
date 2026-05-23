"""BSC Forge — Forge Ajan (tool-calling döngüsü)."""
import json
import re
import ast
import operator as _operator
from dataclasses import dataclass
from typing import AsyncGenerator

from google import genai
from google.genai import types
from groq import AsyncGroq

from config import settings
from services.llm_manager import llm_manager
from services.provider_utils import (
    cascade_from,
    fallback_notice,
    is_fallbackable_error,
    is_ollama_available,
    model_active_event,
    model_for_provider,
    PROVIDER_LABELS,
)
from services.tools import TOOL_SCHEMAS, execute_tool, write_file

MAX_AGENT_STEPS = 2

SYSTEM_PROMPT = """Sen BSC Forge yapay zeka ajanısın. Yardımsever, bilgili ve dostçasın.
Varsayılan yanıt dili Türkçe; kullanıcı başka dilde yazarsa o dilde yanıt ver.
Kullanıcının projesi: {workspace}

## Ne zaman doğrudan yanıt verirsin (araç gerekmez)
- Genel bilgi: coğrafya, tarih, matematik, fen, kültür
- Teknoloji önerileri: hangi API, kütüphane, araç kullanılır, fiyatlandırma, karşılaştırma
- Programlama: kod yaz, açıkla, hata ayıkla
- Tavsiye ve fikir soruları
- Canlı veri gerektiren ama yaklaşık yanıt verilebilecek sorular (örn. "İzmir ile X arası kaç km")

Bu tür sorularda **eğitim verindeki bilgiyi kullan**; "internet erişimim yok" veya
"sadece dosyalarla çalışabilirim" deme — bu yanlış ve kullanıcıyı engeller.

Canlı/gerçek zamanlı veri gerektiren durumlarda (anlık hava, borsa fiyatı vb.)
şunu söyle: "Şu an canlı veriye erişimim yok, ancak [X] API'sini kullanabilirsin."
Ardından uygun ücretsiz/açık API öner.

## Ne zaman araç kullanırsın
- list_directory: klasör içeriğini listele (sadece kullanıcı içeriği görmek istediğinde)
- read_file: belirli bir dosyanın içeriğini oku (kullanıcı o dosyayı sorduğunda)
- write_file: dosya oluştur veya güncelle (kullanıcı onayı gerektirir)

## Dosya/sayfa/kod oluşturma kuralları (ÇOK ÖNEMLİ)
Kullanıcı bir dosya, web sayfası, HTML, CSS, kod parçası veya site üretmeni
istediğinde **doğrudan write_file aracını çağır**. Tasarımı veya yapıyı önce
metin olarak anlatma; içeriği hazırla ve write_file ile yaz.

- "X.html oluştur" → write_file(path="X.html", content="<tam HTML kodu>")
- "Bir landing page yap" → write_file(path="index.html", content="<...>")
- "Bana bir Python script yaz" → write_file(path="script.py", content="<...>")

Önce list_directory veya read_file çağırma — gereksizdir. Kullanıcı zaten onay
verecek ve istediği yola taşıyabilecek.

## Kurallar
- Görmediğin dosya içeriğini tahmin etme; araçla oku.
- Aynı araç + yolu tekrar çağırma.
- Yanıtlarda Markdown kullanabilirsin."""


@dataclass
class ToolCall:
    name: str
    args: dict


@dataclass
class StepResult:
    tool_calls: list[ToolCall]
    direct_text: str | None = None
    quota_fallback: bool = False
    fallback_from: str | None = None
    fallback_to: str | None = None


class ForgeAgent:
    """ReAct tarzı ajan: araç çağır → sonuç al → yanıt üret."""

    def _system_message(self) -> dict:
        return {
            "role": "system",
            "content": SYSTEM_PROMPT.format(workspace=settings.WORKSPACE_ROOT),
        }

    def _try_simple_math(self, text: str) -> str | None:
        """Basit aritmetik ifadelerini yerelde çöz (örn. "2 kere 2 kaç eder", "3+4")."""
        if not text or len(text) > 200:
            return None

        s = text.lower().strip()
        # Kısa doğal dil kalıplarını operatörlere çevir
        s = re.sub(r"kaç\s*(eder|yapar)\??", "", s)
        s = s.replace(" kere ", "*")
        s = s.replace(" çarp ", "*")
        s = s.replace(" çarpı ", "*")
        s = s.replace(" artı ", "+")
        s = s.replace(" eksi ", "-")
        s = s.replace(" bölü ", "/")
        s = s.replace(" böl ", "/")
        s = s.replace(" / ", "/")
        # Temizle: sadece rakamlar, parantez ve operatörler kalsın
        cleaned = re.sub(r"[^0-9\.\+\-\*\/\(\)\s]", "", s).strip()
        if not cleaned:
            return None

        # Güvenli değerlendirme: AST ile yalnızca basit aritmetik izni ver
        try:
            node = ast.parse(cleaned, mode="eval")
        except Exception:
            return None

        allowed_ops = {
            ast.Add: _operator.add,
            ast.Sub: _operator.sub,
            ast.Mult: _operator.mul,
            ast.Div: _operator.truediv,
            ast.Pow: _operator.pow,
            ast.USub: _operator.neg,
        }

        def _eval(n):
            if isinstance(n, ast.Expression):
                return _eval(n.body)
            if isinstance(n, ast.Constant) and isinstance(n.value, (int, float)):
                return n.value
            if isinstance(n, ast.BinOp):
                if type(n.op) not in allowed_ops:
                    raise ValueError("Operator not allowed")
                return allowed_ops[type(n.op)](_eval(n.left), _eval(n.right))
            if isinstance(n, ast.UnaryOp) and type(n.op) in allowed_ops:
                return allowed_ops[type(n.op)](_eval(n.operand))
            raise ValueError("Unsupported expression")

        try:
            result = _eval(node)
        except Exception:
            return None

        # Boşlukları kısaltılmış orijinal ifade ile kullanıcının görebileceği cevap oluştur
        display = cleaned
        # Eğer sonuç tam sayıysa tam sayı göster
        if isinstance(result, float) and result.is_integer():
            result = int(result)

        return f"{display} = {result}"

    def _build_messages(self, user_message: str, history: list[dict]) -> list[dict]:
        messages = [self._system_message()]
        for msg in history:
            if msg.get("role") in ("user", "assistant"):
                messages.append({"role": msg["role"], "content": msg["content"]})
        messages.append({"role": "user", "content": user_message})
        return messages

    def _tool_label(self, name: str, args: dict) -> str:
        if name == "list_directory":
            path = args.get("path", ".") or "."
            return f"📂 Klasör listeleniyor: `{path}`"
        if name == "read_file":
            path = args.get("path", "")
            return f"📄 Dosya okunuyor: `{path}`"
        if name == "write_file":
            path = args.get("path", "")
            return f"✏️ Dosya yazılıyor: `{path}`"
        return f"🔧 {name}"

    def _gemini_tools(self) -> list[types.Tool]:
        declarations = [
            types.FunctionDeclaration(
                name=s["name"],
                description=s["description"],
                parameters=s["parameters"],
            )
            for s in TOOL_SCHEMAS
        ]
        return [types.Tool(function_declarations=declarations)]

    def _gemini_contents(self, messages: list[dict]) -> list[types.Content]:
        contents = []
        for msg in messages:
            role = msg["role"]
            if role == "system":
                role = "user"
            if role not in ("user", "model", "assistant"):
                continue
            gemini_role = "user" if role in ("user", "system") else "model"
            contents.append(
                types.Content(
                    role=gemini_role,
                    parts=[types.Part(text=msg["content"])],
                )
            )
        return contents

    def _local_tool_summary(self, messages: list[dict]) -> str | None:
        """Yalnızca list_directory kullanıldıysa LLM çağrısı olmadan özet üret (kota tasarrufu)."""
        list_bodies: list[str] = []
        read_used = False
        for m in messages:
            content = m.get("content", "")
            if m.get("role") != "user":
                continue
            if content.startswith("Araç sonucu (list_directory):"):
                list_bodies.append(content.split("\n\n", 1)[-1].strip())
            if content.startswith("Araç sonucu (read_file):"):
                read_used = True
        if not list_bodies or read_used:
            return None
        combined = "\n\n---\n\n".join(list_bodies)
        return (
            "**Klasör içeriği:**\n\n"
            f"{combined}\n\n"
            "_Özet araç çıktısından oluşturuldu (ek model isteği yok)._"
        )

    def _heuristic_tool_calls(self, user_message: str) -> list[ToolCall]:
        """Bulut kotası bitince basit dosya listesi istekleri için yerel araç."""
        msg = user_message.lower()
        if not any(w in msg for w in ("listele", "listeler", "dosya", "klasör", "içindeki", "göster")):
            return []
        path = "."
        if "backend" in msg:
            path = "backend"
        elif "frontend" in msg:
            path = "frontend"
        return [ToolCall("list_directory", {"path": path})]

    async def _step_ollama(self, messages: list[dict]) -> StepResult:
        """Ollama tool API desteklemez; basit isteklerde sezgisel araç."""
        user_msg = next(
            (m["content"] for m in reversed(messages) if m.get("role") == "user"),
            "",
        )
        heuristic = self._heuristic_tool_calls(user_msg)
        if heuristic:
            return StepResult(tool_calls=heuristic)
        return StepResult(tool_calls=[], direct_text=None)

    async def _step_gemini(self, messages: list[dict], model: str) -> StepResult:
        if not settings.is_gemini_configured():
            raise RuntimeError("Gemini yapılandırılmamış")

        client = genai.Client(api_key=settings.GEMINI_API_KEY)
        response = client.models.generate_content(
            model=model,
            contents=self._gemini_contents(messages),
            config=types.GenerateContentConfig(
                tools=self._gemini_tools(),
                temperature=0.4,
                max_output_tokens=4096,
            ),
        )

        tool_calls: list[ToolCall] = []
        texts: list[str] = []

        if not response.candidates:
            return StepResult(tool_calls=[], direct_text="[HATA] Gemini boş yanıt döndü.")

        for part in response.candidates[0].content.parts:
            if part.function_call:
                fc = part.function_call
                args = dict(fc.args) if fc.args else {}
                tool_calls.append(ToolCall(name=fc.name, args=args))
            elif part.text:
                texts.append(part.text)

        direct = "\n".join(texts).strip() or None
        return StepResult(tool_calls=tool_calls, direct_text=direct if not tool_calls else None)

    def _groq_tools(self) -> list[dict]:
        return [
            {
                "type": "function",
                "function": {
                    "name": s["name"],
                    "description": s["description"],
                    "parameters": s["parameters"],
                },
            }
            for s in TOOL_SCHEMAS
        ]

    async def _step_groq(self, messages: list[dict], model: str) -> StepResult:
        if not settings.is_groq_configured():
            return StepResult(tool_calls=[], direct_text=None)

        client = AsyncGroq(api_key=settings.GROQ_API_KEY)
        groq_messages = [
            {"role": m["role"], "content": m["content"]}
            for m in messages
            if m["role"] in ("system", "user", "assistant")
        ]

        try:
            completion = await client.chat.completions.create(
                model=model,
                messages=groq_messages,
                tools=self._groq_tools(),
                tool_choice="auto",
                temperature=0.4,
                max_tokens=4096,
            )
        except Exception as e:
            if is_fallbackable_error(e):
                raise
            return StepResult(tool_calls=[], direct_text=f"[HATA] Groq: {e}")

        msg = completion.choices[0].message
        tool_calls: list[ToolCall] = []

        if msg.tool_calls:
            for tc in msg.tool_calls:
                raw_args = tc.function.arguments or "{}"
                try:
                    args = json.loads(raw_args) if isinstance(raw_args, str) else dict(raw_args)
                except json.JSONDecodeError:
                    args = {}
                tool_calls.append(ToolCall(name=tc.function.name, args=args))

        direct = (msg.content or "").strip() or None
        return StepResult(tool_calls=tool_calls, direct_text=direct if not tool_calls else None)

    async def _run_step_provider(
        self, messages: list[dict], provider: str, model: str | None
    ) -> StepResult:
        if provider == "gemini":
            return await self._step_gemini(
                messages, model_for_provider("gemini", model)
            )
        if provider == "groq":
            return await self._step_groq(messages, model_for_provider("groq", model))
        return await self._step_ollama(messages)

    async def _step_with_cascade(
        self, messages: list[dict], start_provider: str, model: str | None
    ) -> StepResult:
        """Gemini → Groq → Ollama (araç adımı)."""
        chain = cascade_from(start_provider)
        last_error: Exception | None = None

        for i, prov in enumerate(chain):
            if prov == "ollama" and not await is_ollama_available():
                last_error = RuntimeError("Ollama çalışmıyor")
                continue
            try:
                result = await self._run_step_provider(messages, prov, model)
                if i > 0:
                    result.quota_fallback = True
                    result.fallback_from = chain[i - 1]
                    result.fallback_to = prov
                return result
            except Exception as e:
                last_error = e
                if is_fallbackable_error(e) and i < len(chain) - 1:
                    continue
                break

        user_msg = next(
            (m["content"] for m in reversed(messages) if m.get("role") == "user"),
            "",
        )
        heuristic = self._heuristic_tool_calls(user_msg)
        if heuristic:
            return StepResult(
                tool_calls=heuristic,
                quota_fallback=True,
                fallback_from=chain[0] if chain else start_provider,
                fallback_to="yerel araç",
            )

        err = str(last_error) if last_error else "Bilinmeyen hata"
        return StepResult(tool_calls=[], direct_text=f"[HATA] {err[:400]}")

    def _append_tool_exchange(
        self, messages: list[dict], call: ToolCall, result: str
    ) -> None:
        """LLM geçmişine araç çağrısı ve sonucunu ekle."""
        messages.append({
            "role": "assistant",
            "content": f"[Araç: {call.name}({json.dumps(call.args, ensure_ascii=False)})]",
        })
        messages.append({
            "role": "user",
            "content": f"Araç sonucu ({call.name}):\n\n{result}",
        })

    async def _stream_events(
        self, messages: list[dict], provider: str, model: str | None
    ) -> AsyncGenerator[dict, None]:
        async for event in llm_manager.stream_with_notices(
            messages, provider=provider, model=model
        ):
            yield event

    def _build_messages_with_prompt(
        self, user_message: str, history: list[dict], system_prompt: str | None
    ) -> list[dict]:
        prompt = system_prompt or SYSTEM_PROMPT.format(workspace=settings.WORKSPACE_ROOT)
        messages = [{"role": "system", "content": prompt}]
        for msg in history:
            if msg.get("role") in ("user", "assistant"):
                messages.append({"role": msg["role"], "content": msg["content"]})
        messages.append({"role": "user", "content": user_message})
        return messages

    async def run(
        self,
        user_message: str,
        history: list[dict],
        provider: str = "gemini",
        model: str | None = None,
        system_prompt: str | None = None,
        tools_enabled: list[str] | None = None,
    ) -> AsyncGenerator[dict, None]:
        """Ajan döngüsü. Olaylar: tool, token, error."""
        messages = self._build_messages_with_prompt(user_message, history, system_prompt)

        # Basit aritmetik sorularını yerelde çöz (hızlı cevap, dış API çağrısı yok)
        math_answer = self._try_simple_math(user_message)
        if math_answer:
            yield {"type": "token", "content": math_answer}
            return
        effective_provider = provider
        effective_model = model

        # Ürün konfigürasyonuna göre izin verilen araçlar
        allowed_tools: set[str] | None = (
            set(tools_enabled) if tools_enabled is not None else None
        )

        tools_used = False
        only_list_tools = True
        for _ in range(MAX_AGENT_STEPS):
            step = await self._step_with_cascade(
                messages, effective_provider, effective_model
            )

            if step.quota_fallback and step.fallback_from and step.fallback_to:
                if step.fallback_to == "yerel araç":
                    yield {
                        "type": "fallback",
                        "content": (
                            f"⚠️ **{step.fallback_from}** limiti doldu; "
                            "**yerel dosya aracı** ile devam ediliyor."
                        ),
                    }
                else:
                    yield {
                        "type": "fallback",
                        "content": fallback_notice(step.fallback_from, step.fallback_to),
                    }
                effective_provider = (
                    step.fallback_to
                    if step.fallback_to in ("gemini", "groq", "ollama")
                    else effective_provider
                )
                effective_model = model_for_provider(effective_provider, effective_model)
                if step.fallback_to in ("gemini", "groq", "ollama"):
                    yield model_active_event(
                        effective_provider,
                        effective_model,
                        label=f"{PROVIDER_LABELS.get(effective_provider, effective_provider)} · {effective_model}",
                    )

            if step.tool_calls:
                tools_used = True
                seen: set[str] = set()
                for call in step.tool_calls:
                    # Ürünün izin vermediği araçları atla
                    if allowed_tools is not None and call.name not in allowed_tools:
                        continue
                    if call.name != "list_directory":
                        only_list_tools = False
                    key = f"{call.name}:{json.dumps(call.args, sort_keys=True, ensure_ascii=False)}"
                    if key in seen:
                        continue
                    seen.add(key)

                    # write_file → onay gerektirir; frontend'e bildir ve dur
                    if call.name == "write_file":
                        path = call.args.get("path", "")
                        content = call.args.get("content", "")
                        preview_lines = content.split("\n")[:25]
                        preview = "\n".join(preview_lines)
                        if len(content.split("\n")) > 25:
                            preview += f"\n… ({len(content.split(chr(10))) - 25} satır daha)"
                        yield {
                            "type": "approval_request",
                            "tool": "write_file",
                            "path": path,
                            "content": content,
                            "preview": preview,
                        }
                        return  # Agent durur; WebSocket onay yanıtını bekler

                    yield {"type": "tool", "content": self._tool_label(call.name, call.args)}
                    result = execute_tool(call.name, call.args)
                    self._append_tool_exchange(messages, call, result)

                # Sadece klasör listeleme → ikinci API turu yok (kota tasarrufu)
                if only_list_tools:
                    local = self._local_tool_summary(messages)
                    if local:
                        yield model_active_event("forge", "local-summary", label="Yerel özet (araç)")
                        yield {"type": "token", "content": local}
                        return
                continue

            # Araç kullanılmadıysa doğrudan kısa yanıt
            if not tools_used and step.direct_text:
                yield {"type": "token", "content": step.direct_text}
                return

            break

        # Araç sonrası: mümkünse yerel özet (Gemini kotası korunur)
        if tools_used:
            local = self._local_tool_summary(messages)
            if local:
                yield model_active_event("forge", "local-summary", label="Yerel özet (araç)")
                yield {"type": "token", "content": local}
                return

            messages.append({
                "role": "user",
                "content": (
                    "Yukarıdaki araç sonuçlarına göre kullanıcıya Türkçe, net ve kısa özet ver. "
                    "Dosya listesini madde madde yaz. Aynı bilgiyi tekrarlama."
                ),
            })

        async for event in self._stream_events(
            messages, effective_provider, effective_model
        ):
            yield event


forge_agent = ForgeAgent()
