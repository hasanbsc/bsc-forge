"""BSC Forge — Forge Ajan (ReAct döngüsü, orkestrasyon).

Bu modül yalnızca ajan döngüsünü ve provider fallback'ini yönetir.
- Sistem promptu: services/agent_prompts.py
- Provider adaptörleri: services/providers/{gemini,groq,deepseek,ollama}.py
- Tool çalıştırma: services/tools.py
"""
import ast
import json
import operator as _operator
import re
import time
from typing import AsyncGenerator

from config import settings
from services.agent_prompts import render_system_prompt
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
from services.providers import (
    StepResult,
    ToolCall,
    heuristic_tool_calls,
    step_deepseek,
    step_gemini,
    step_groq,
    step_ollama,
)
from services.tools import execute_tool


class ForgeAgent:
    """ReAct tarzı ajan: araç çağır → sonuç al → yanıt üret."""

    # ─── Sistem promptu ─────────────────────────────────────

    def _system_prompt(self, active_files_section: str = "") -> str:
        return render_system_prompt(
            workspace=str(settings.WORKSPACE_ROOT),
            active_files_section=active_files_section,
        )

    # ─── Yerel matematik (kota tasarrufu) ──────────────────

    def _try_simple_math(self, text: str) -> str | None:
        """Basit aritmetik ifadelerini yerelde çöz (örn. "2 kere 2 kaç eder", "3+4")."""
        if not text or len(text) > 200:
            return None
        # 10+ kelimelik cümle aritmetik değil ("Eryılmaz Emlak ..., 6 ilan" gibi)
        if len(text.split()) > 10:
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
        cleaned = re.sub(r"[^0-9\.\+\-\*\/\(\)\s]", "", s).strip()
        if not cleaned:
            return None
        if not re.search(r"[+\-*/]", cleaned):
            return None

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

        if isinstance(result, float) and result.is_integer():
            result = int(result)
        return f"{cleaned} = {result}"

    # ─── Mesaj inşası ───────────────────────────────────────

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

    # ─── Metin içinden tool çağrısı kurtarma ────────────────
    # Bazı modeller (özellikle Groq Llama 3.3 70B) tool çağrısını gerçek
    # JSON tool_call yerine metne `<function(NAME)>{...}</function>` formatında
    # yazıyor. Bu durumu kurtarmak için metni parse edip ToolCall'a çeviriyoruz.

    _FUNCTION_TAG_PATTERN = re.compile(
        r"<function\(\s*(\w+)\s*\)>\s*(\{.*?\})\s*</function>",
        re.DOTALL,
    )

    def _recover_tool_calls_from_text(self, text: str) -> list[ToolCall]:
        if not text or "<function(" not in text:
            return []
        recovered: list[ToolCall] = []
        for match in self._FUNCTION_TAG_PATTERN.finditer(text):
            name = match.group(1).strip()
            raw_json = match.group(2)
            args: dict | None = None
            try:
                args = json.loads(raw_json)
            except json.JSONDecodeError:
                args = None
            if args is None:
                path_m = re.search(r'"path"\s*:\s*"([^"]+)"', raw_json)
                content_m = re.search(
                    r'"content"\s*:\s*"(.*)"\s*\}\s*$', raw_json, re.DOTALL
                )
                if path_m and content_m:
                    content = content_m.group(1)
                    content = (
                        content.replace("\\n", "\n")
                        .replace("\\t", "\t")
                        .replace('\\"', '"')
                        .replace("\\\\", "\\")
                    )
                    args = {"path": path_m.group(1), "content": content}
            if args:
                recovered.append(ToolCall(name=name, args=args))
        return recovered

    # ─── Aktif dosya izleme ────────────────────────────────
    # Backtick içinde boşluk dahil her şey, ya da backtick'siz boşluksuz path
    _WRITE_TRACE_PATTERN = re.compile(
        r"(?:`([^`]+\.[a-zA-Z0-9]{1,6})`|([^\s`'\"<>]+\.[a-zA-Z0-9]{1,6}))\s*"
        r"(?:bilgisayara\s+kaydedildi|kaydedildi|oluşturuldu|güncellendi|yazıldı)",
        re.IGNORECASE,
    )

    def _extract_active_files(self, history: list[dict], limit: int = 3) -> list[str]:
        """Önceki asistan mesajlarından son write_file yollarını çıkar (en yeni → eski)."""
        seen: list[str] = []
        for msg in reversed(history):
            if msg.get("role") != "assistant":
                continue
            content = msg.get("content") or ""
            for match in self._WRITE_TRACE_PATTERN.finditer(content):
                path = (match.group(1) or match.group(2) or "").strip().strip("`'\"")
                if path and path not in seen:
                    seen.append(path)
                    if len(seen) >= limit:
                        return seen
        return seen

    def _active_files_section(self, history: list[dict]) -> str:
        files = self._extract_active_files(history)
        if not files:
            return ""
        if len(files) == 1:
            paths = f"`{files[0]}`"
        else:
            paths = ", ".join(f"`{p}`" for p in files)
        return (
            "\n## Aktif dosyalar (bu oturumda dokunulan dosyalar)\n"
            f"En son üzerinde çalıştığın dosya: {paths} (ilki en yeni). "
            "Kullanıcı bu oturumda bir düzenleme isterse **yeni bir dosya AÇMA** — "
            "yukarıdaki yolu yeniden kullan, önce `read_file` ile içeriği oku, "
            "yalnızca istenen değişikliği uygula, kalanı koru."
        )

    def _build_messages(
        self, user_message: str, history: list[dict], system_prompt: str | None
    ) -> list[dict]:
        active_section = self._active_files_section(history)
        if system_prompt:
            prompt = system_prompt + (f"\n{active_section}" if active_section else "")
        else:
            prompt = self._system_prompt(active_section)
        messages = [{"role": "system", "content": prompt}]
        for msg in history:
            if msg.get("role") in ("user", "assistant"):
                messages.append({"role": msg["role"], "content": msg["content"]})
        messages.append({"role": "user", "content": user_message})
        return messages

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

    # ─── Provider dispatch ─────────────────────────────────

    async def _run_step_provider(
        self, messages: list[dict], provider: str, model: str | None
    ) -> StepResult:
        if provider == "gemini":
            return await step_gemini(messages, model_for_provider("gemini", model))
        if provider == "groq":
            return await step_groq(messages, model_for_provider("groq", model))
        if provider == "deepseek":
            return await step_deepseek(messages, model_for_provider("deepseek", model))
        return await step_ollama(messages)

    async def _step_with_cascade(
        self, messages: list[dict], start_provider: str, model: str | None
    ) -> StepResult:
        """Fallback zinciri: Gemini → Groq → DeepSeek → Ollama (araç adımı)."""
        chain = cascade_from(start_provider)
        last_error: Exception | None = None

        for i, prov in enumerate(chain):
            if prov == "ollama" and not await is_ollama_available():
                last_error = RuntimeError("Ollama çalışmıyor")
                continue
            # Yalnızca orijinal provider'a uygun preferred modeli koru;
            # cascade'de farklı provider'a geçilince modeli sıfırla
            # ki "gemini-2.5-flash"i Ollama'ya gönderme bug'ı tekrar etmesin.
            prov_model = model if prov == start_provider else None
            try:
                result = await self._run_step_provider(messages, prov, prov_model)
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
        heuristic = heuristic_tool_calls(user_msg)
        if heuristic:
            return StepResult(
                tool_calls=heuristic,
                quota_fallback=True,
                fallback_from=chain[0] if chain else start_provider,
                fallback_to="yerel araç",
            )

        err = str(last_error) if last_error else "Bilinmeyen hata"
        return StepResult(tool_calls=[], direct_text=f"[HATA] {err[:400]}")

    # ─── Streaming yardımcısı ──────────────────────────────

    async def _stream_events(
        self, messages: list[dict], provider: str, model: str | None
    ) -> AsyncGenerator[dict, None]:
        async for event in llm_manager.stream_with_notices(
            messages, provider=provider, model=model
        ):
            yield event

    # ─── Ana döngü ─────────────────────────────────────────

    async def run(
        self,
        user_message: str,
        history: list[dict],
        provider: str = "gemini",
        model: str | None = None,
        system_prompt: str | None = None,
        tools_enabled: list[str] | None = None,
    ) -> AsyncGenerator[dict, None]:
        """Ajan döngüsü. Olaylar: tool, token, error, approval_request, fallback."""
        messages = self._build_messages(user_message, history, system_prompt)

        # Basit aritmetik sorularını yerelde çöz (dış API çağrısı yok)
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
        for _ in range(settings.MAX_AGENT_STEPS):
            step = await self._step_with_cascade(
                messages, effective_provider, effective_model
            )

            # Recovery: bazı modeller tool çağrısını metne yazıyor
            # (`<function(write_file)>{...}</function>`).
            if not step.tool_calls and step.direct_text:
                recovered = self._recover_tool_calls_from_text(step.direct_text)
                if recovered:
                    step.tool_calls = recovered
                    step.direct_text = None

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
                    if step.fallback_to in ("gemini", "groq", "deepseek", "ollama")
                    else effective_provider
                )
                effective_model = model_for_provider(effective_provider, effective_model)
                if step.fallback_to in ("gemini", "groq", "deepseek", "ollama"):
                    yield model_active_event(
                        effective_provider,
                        effective_model,
                        label=f"{PROVIDER_LABELS.get(effective_provider, effective_provider)} · {effective_model}",
                    )

            if step.tool_calls:
                tools_used = True
                seen: set[str] = set()
                write_calls: list[ToolCall] = []
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

                    # write_file çağrıları toplanır; diğerleri hemen çalıştırılır
                    if call.name == "write_file":
                        write_calls.append(call)
                        continue

                    yield {"type": "tool", "content": self._tool_label(call.name, call.args)}
                    result = execute_tool(call.name, call.args)
                    self._append_tool_exchange(messages, call, result)

                # Tüm write_file'ları sırayla approval kuyruğuna yay, sonra dur.
                # Frontend kuyruğu yönetir; agent burada blokesiz biter.
                if write_calls:
                    batch_id = f"batch-{int(time.time() * 1000)}"
                    total = len(write_calls)
                    for i, call in enumerate(write_calls, start=1):
                        path = call.args.get("path", "")
                        content = call.args.get("content", "")
                        lines = content.split("\n")
                        preview_lines = lines[:25]
                        preview = "\n".join(preview_lines)
                        if len(lines) > 25:
                            preview += f"\n… ({len(lines) - 25} satır daha)"
                        yield {
                            "type": "approval_request",
                            "tool": "write_file",
                            "path": path,
                            "content": content,
                            "preview": preview,
                            "batch_id": batch_id,
                            "batch_index": i,
                            "batch_total": total,
                        }
                    return  # Agent durur; frontend approval queue'sunu işler

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
