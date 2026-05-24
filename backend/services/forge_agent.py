"""BSC Forge — Forge Ajan (tool-calling döngüsü)."""
import json
import re
import ast
import time
import operator as _operator
from dataclasses import dataclass
from typing import AsyncGenerator

import httpx
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

MAX_AGENT_STEPS = 5  # Çoklu dosya akışında modele 4+ adım veriyoruz

SYSTEM_PROMPT = """Sen BSC Forge yapay zeka ajanısın. Yardımsever, bilgili ve dostçasın.
Varsayılan yanıt dili Türkçe; kullanıcı başka dilde yazarsa o dilde yanıt ver.
Kullanıcının projesi: {workspace}
{active_files_section}

## Kendini tanıtırken
Birisi "BSC Forge nedir / kendini tanıt" derse şu çerçevede yanıt ver:
Sen Hasan'ın kişisel yapay zeka portalısın — birden fazla LLM sağlayıcısını
(Gemini, Groq, DeepSeek, yerel Ollama modelleri) tek bir arayüzde birleştiren,
gelen göreve göre en uygun modeli otomatik seçen ve gerektiğinde dosya
okuma/yazma araçlarını kullanan bir asistansın. Sıcak ve kısa bir paragrafla
anlat; teknik mimari listesi dökme, gereksiz uzatma, başka platformlarla
karşılaştırma yapma.

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

İlk üretimde list_directory veya read_file çağırma — gereksizdir. Kullanıcı
zaten onay verecek ve istediği yola taşıyabilecek.

## Düzenleme akışı (mevcut dosyayı GÜNCELLE — yeni dosya AÇMA)
Bu oturumda zaten bir dosya ürettiysen ve kullanıcı sonraki mesajda **düzenleme
talep ediyorsa** (örnek tetikleyiciler: "değiştir, ekle, çıkar, düzenle, düzelt,
yenile, modern yap, renkleri güncelle, fotoğraf ekle, başlığı şu yap, şu cümleyi
şuna çevir"), şunu yap:

1. **AYNI yol** ile devam et — `index2.html`, `index3.html` gibi yeni dosya
   AÇMA. Yukarıda "Aktif dosya" bölümü bir yol gösteriyorsa onu kullan.
2. Önce `read_file(path=<aktif_yol>)` ile mevcut içeriği oku.
3. **Sadece kullanıcının istediği değişikliği** uygula. Diğer her şeyi
   (başlıklar, kartlar, stil, görseller, footer, ilan sayısı) **olduğu gibi
   koru**. "Cümleyi değiştir" denmişse sadece o cümle değişsin; ekran düzeni,
   renkler, görseller dokunulmaz kalsın.
4. Güncellenmiş tam içeriği `write_file(path=<aynı_yol>, content=...)` ile yaz.

Yeni bir dosya, ancak kullanıcı **açıkça** "yeni sayfa oluştur", "ayrı bir
hakkımızda.html aç", "ikinci bir versiyon yap" gibi yeni dosya isteğinde
bulunduğunda açılır.

## Web sitesi / HTML üretirken kalite kuralları
Site / sayfa istendiğinde aşağıdaki standartları MUTLAKA uygula. Yarım iş,
basit görünümlü tek-kart sayfa **kabul edilmez**.

**1. Marka adı tutarlılığı**
Kullanıcı bir isim verdiyse (örn. "Eryılmaz Emlak", "BSC Emlak") `<title>`,
header logosu, navbar, footer copyright, hero altyazısı, e-posta domaini,
about bölümü — HEPSİNDE bu isim. Yer tutucu ("Şirket Adı", "Brand", "Logo")
asla yazma. Marka verilmediyse kısa, uygun bir tane uydur ve tutarlı kullan.

**2. Görseller — placeholder.com YASAK, MUTLAKA gerçek görsel**
Boş gri kutu yerine her zaman gerçek görsel URL'i:
- `https://images.unsplash.com/photo-<id>?w=800&q=80` — Unsplash bilinen foto id'leri (varsa)
- `https://source.unsplash.com/featured/800x500/?<kelimeler>` (örn. `?villa,luxury,turkey`)
- `https://picsum.photos/seed/<benzersiz>/<w>/<h>` (her seed farklı görsel)
- Hero/cover için `https://images.unsplash.com/photo-1568605114967-8130f3a36994?w=1600&q=80` gibi
Her kart için **farklı seed/keyword** — hepsi aynı görsel olmasın. `<img>` mutlaka `alt`, `loading="lazy"`.

**3. Konu sadakati**
"Emlak" istenmişse hepsi ev/daire/villa; "restoran" istenmişse menü yemek;
"e-ticaret" istenmişse ürün. Karıştırma. Kategori dışı item koyma.

**4. Türkiye bağlamı**
Türkçe site/Türk işletme: gerçek Türkiye şehir+mahalle ("Beşiktaş/İstanbul",
"Çankaya/Ankara", "Konak/İzmir"), Türk telefon (`+90 5XX XXX XX XX`), TL fiyat
(`₺ 4.500.000` veya `4.500.000 TL`), Türkçe etiketler ("Yatak Odası", "Banyo",
"Eşyalı", "Otopark"). Yabancı yer adı / İngilizce label kullanma.

**5. Minimum sayfa derinliği (ZORUNLU)**

Bir site / landing page üretirken sayfada **en az şu bölümler** olsun:
1. `<header>` + sticky `<nav>` (en az 5 link: Anasayfa, Hizmetler/Kategoriler, İlanlar/Ürünler, Hakkımızda, İletişim)
2. `<section class="hero">` — büyük başlık, alt metin, arama kutusu (form), 1+ CTA butonu, arka plan görseli
3. **Ana liste**: kullanıcı X öğe demişse X tane, demediyse **8-12 öğe**. Her öğe: görsel + başlık + 2-3 satır açıklama + fiyat/etiket + "Detay" butonu
4. **Filtre/arama bandı**: en az 3-4 dropdown (kategori, fiyat aralığı, lokasyon, oda sayısı vb. — alana göre)
5. **Hizmetler/Özellikler** bölümü: 3-4 ikonlu kart ("Uzman Danışmanlık", "Hızlı Süreç" vb.)
6. **Hakkımızda** kısa bölümü (paragraf + istatistik kartları: "500+ Mutlu Müşteri", "10 Yıl Tecrübe")
7. **Müşteri yorumları**: 3 testimonial kartı (avatar + ad + yıldız + yorum)
8. **İletişim**: form (ad, e-posta, telefon, mesaj) + harita iframe (`https://maps.google.com/maps?q=...&output=embed`) + adres/telefon/saat
9. `<footer>`: 3-4 sütun (Kurumsal, Hizmetler, İletişim, Sosyal Medya ikonları), alt copyright

**6. Modern görsel kalite (ZORUNLU)**

- CSS değişkenleri (`:root { --primary: ...; --accent: ...; }`) ile renk paleti
- Modern font: `<link href="https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&family=Poppins:wght@600;700;800&display=swap" rel="stylesheet">` ya da benzeri
- Layout: **CSS Grid + Flexbox** (eski float yok)
- Kart tasarımı: yumuşak gölge (`box-shadow: 0 10px 30px rgba(0,0,0,0.08)`), `border-radius: 12-16px`, hover'da `transform: translateY(-4px)` + büyüyen gölge
- Buton: gradient veya solid renk, hover'da renk/gölge geçişi, `transition: all 0.3s`
- Tipografi hiyerarşisi: h1 ≥ 48px, h2 ≥ 32px, body 16-18px, satır yüksekliği 1.6
- Responsive: `@media (max-width: 768px)` ile mobil uyum, nav hamburger menü davranışı
- Lucide/Heroicons emoji yerine `<svg>` ikon (emlak: 🏠 yerine ev svg'si)

**7. İçerik kalitesi**

- Her ilan/ürün için **gerçekçi, farklı** açıklama (kopya-yapıştır yok). Türkçe akıcı.
- Fiyatlar mantıklı bir aralıkta (emlak: 1.500.000 - 25.000.000 TL gibi)
- Konum farkı: hepsi aynı semt olmasın
- Müşteri yorumları gerçekçi isimlerle ("Ayşe K., Mimar", "Mehmet Y., Doktor")

**8. Çoklu dosya yapısı (Codex tarzı)**
Bir site/uygulama istendiğinde **birden fazla `write_file` çağrısı** yap —
modüler dosyalar üret:

- `index.html` (içeride `<link rel="stylesheet" href="style.css">` +
  gerekirse `<script src="script.js" defer></script>` referansları)
- `style.css` (tüm stiller, CSS değişkenleri, responsive `@media`)
- `script.js` (etkileşim varsa: filtre tab'leri, hamburger menü, form
  validation, scroll animasyonu vb. — yoksa atla)

Birden fazla sayfa istendiyse her biri ayrı `.html` dosyası (`hakkimizda.html`,
`menu.html`) + ortak `style.css`. Görseller URL referanslı (Unsplash/Picsum),
font CDN dışında **harici dosya isteme**.

**Çoklu dosya zorunluluğu — DİKKAT**

Bir site ürettiğinde **sadece bir dosya yazıp durma**. `index.html` `<link
rel="stylesheet" href="style.css">` referansı içeriyorsa `style.css` dosyasını
da yazmak ZORUNDASIN. Aynı şekilde `<script src="script.js">` varsa
`script.js`'i de yaz. Aksi takdirde kullanıcının elinde stilsiz / işlevsiz
bir HTML kalır.

Şu sırayı izle (her birini ayrı `write_file` çağrısı olarak):
1. `index.html` — referansları içerir
2. `style.css` — TÜM stiller burada
3. `script.js` — etkileşim varsa (filter tab, hamburger menü, form vb.)

Bir dosya yazdıktan sonra "bitti" deme — kullanıcının istediği tüm dosyaları
yazana kadar devam et. Forge her dosya için ayrı onay isteyecek; kullanıcı
"Tümünü Kabul Et" diyebilir.

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

    def _render_system_prompt(self, active_files_section: str = "") -> str:
        # NOT: `.format()` kullanmıyoruz çünkü promptta CSS örneği gibi
        # süslü parantezli içerik var (`:root { --primary: ... }`) — placeholder
        # gibi yorumlanır ve KeyError patlar. Düz replace kaçırma sorununu önler.
        return (
            SYSTEM_PROMPT
            .replace("{workspace}", str(settings.WORKSPACE_ROOT))
            .replace("{active_files_section}", active_files_section)
        )

    def _system_message(self) -> dict:
        return {
            "role": "system",
            "content": self._render_system_prompt(""),
        }

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
        # Temizle: sadece rakamlar, parantez ve operatörler kalsın
        cleaned = re.sub(r"[^0-9\.\+\-\*\/\(\)\s]", "", s).strip()
        if not cleaned:
            return None
        # Operatör yoksa bu matematik değil — sadece sayı içeren bir cümle
        if not re.search(r"[+\-*/]", cleaned):
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
            # 1. Önce sade JSON parse
            try:
                args = json.loads(raw_json)
            except json.JSONDecodeError:
                args = None
            # 2. Başarısızsa: path ve content'i ayrı ayrı yakala (Llama bazen
            #    içerikteki çift tırnağı escape etmeyi unutuyor)
            if args is None:
                path_m = re.search(r'"path"\s*:\s*"([^"]+)"', raw_json)
                content_m = re.search(
                    r'"content"\s*:\s*"(.*)"\s*\}\s*$', raw_json, re.DOTALL
                )
                if path_m and content_m:
                    content = content_m.group(1)
                    # JSON escape'lerini gerçek karakterlere çevir
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

    def _heuristic_tool_calls(self, user_message: str) -> list[ToolCall]:
        """Bulut kotası bitince yalnızca AÇIK niyetli dosya listeleme isteklerinde yerel araç."""
        msg = user_message.lower()
        # Açık listeleme niyeti şart — "dosya AÇMA" / "yeni dosya" / "index.html'i güncelle" gibi
        # cümleler tetiklememeli. İki kelimelik fiil+nesne kombinasyonu zorunlu.
        listing_phrases = (
            "klasörü listele", "klasörü göster", "klasörü aç",
            "dosyaları listele", "dosyaları göster",
            "içindekileri listele", "içindekileri göster", "içindeki dosyalar",
            "dizini göster", "dizini listele",
            "list directory", "list files", "show files", "show directory",
            "ls ",
        )
        if not any(p in msg for p in listing_phrases):
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
                # Site/HTML üretimleri kolayca 4-8k token sürüyor; Flash 65k destekler
                max_output_tokens=16384,
            ),
        )

        tool_calls: list[ToolCall] = []
        texts: list[str] = []

        if not response.candidates:
            return StepResult(tool_calls=[], direct_text="[HATA] Gemini boş yanıt döndü.")

        candidate = response.candidates[0]
        # content None olabilir: MAX_TOKENS, SAFETY, RECITATION, MALFORMED_FUNCTION_CALL...
        if candidate.content is None or not candidate.content.parts:
            finish = getattr(candidate, "finish_reason", None)
            reason = getattr(finish, "name", str(finish)) if finish else "bilinmiyor"
            # Fallback'le kurtarılabilecek sebepler — exception fırlat ki
            # cascade (Gemini → Groq → DeepSeek → Ollama) devreye girsin
            fallbackable = {"MALFORMED_FUNCTION_CALL", "MAX_TOKENS", "OTHER", "UNKNOWN"}
            if reason in fallbackable:
                raise RuntimeError(f"Gemini {reason} — fallback gerek")
            # Aksi halde kullanıcıya bilgi (başka modelle çözülemez)
            hint = {
                "SAFETY": "Güvenlik filtresi yanıtı engelledi. İsteği biraz farklı ifade et.",
                "RECITATION": "Model alıntı kısıtına takıldı; isteği yeniden ifade et.",
            }.get(reason, "Yanıt üretilemedi.")
            return StepResult(
                tool_calls=[],
                direct_text=f"[HATA] Gemini yanıt veremedi (sebep: {reason}). {hint}",
            )

        for part in candidate.content.parts:
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

    async def _step_deepseek(self, messages: list[dict], model: str) -> StepResult:
        """DeepSeek (OpenAI-uyumlu) tool-calling adımı."""
        if not settings.is_deepseek_configured():
            return StepResult(tool_calls=[], direct_text=None)

        ds_messages = [
            {"role": m["role"], "content": m["content"]}
            for m in messages
            if m["role"] in ("system", "user", "assistant")
        ]

        url = "https://api.deepseek.com/v1/chat/completions"
        headers = {
            "Authorization": f"Bearer {settings.DEEPSEEK_API_KEY}",
            "Content-Type": "application/json",
        }
        payload = {
            "model": model,
            "messages": ds_messages,
            "tools": self._groq_tools(),  # OpenAI tool şeması — Groq ile birebir aynı
            "tool_choice": "auto",
            "temperature": 0.4,
            "max_tokens": 4096,
        }

        try:
            async with httpx.AsyncClient(timeout=120.0) as client:
                response = await client.post(url, json=payload, headers=headers)
                if response.status_code != 200:
                    body = response.text
                    err = f"Deepseek HTTP {response.status_code}: {body[:300]}"
                    if is_fallbackable_error(err):
                        raise RuntimeError(err)
                    return StepResult(tool_calls=[], direct_text=f"[HATA] {err}")
                data = response.json()
        except httpx.HTTPError as e:
            raise RuntimeError(f"Deepseek bağlantı hatası: {e}") from e
        except Exception as e:
            if is_fallbackable_error(e):
                raise
            return StepResult(tool_calls=[], direct_text=f"[HATA] Deepseek: {e}")

        choices = data.get("choices") or []
        if not choices:
            return StepResult(tool_calls=[], direct_text=None)
        msg = choices[0].get("message", {}) or {}

        tool_calls: list[ToolCall] = []
        for tc in msg.get("tool_calls") or []:
            fn = tc.get("function") or {}
            raw_args = fn.get("arguments") or "{}"
            try:
                args = (
                    json.loads(raw_args) if isinstance(raw_args, str) else dict(raw_args)
                )
            except json.JSONDecodeError:
                args = {}
            name = fn.get("name") or ""
            if name:
                tool_calls.append(ToolCall(name=name, args=args))

        direct = (msg.get("content") or "").strip() or None
        return StepResult(
            tool_calls=tool_calls,
            direct_text=direct if not tool_calls else None,
        )

    async def _run_step_provider(
        self, messages: list[dict], provider: str, model: str | None
    ) -> StepResult:
        if provider == "gemini":
            return await self._step_gemini(
                messages, model_for_provider("gemini", model)
            )
        if provider == "groq":
            return await self._step_groq(messages, model_for_provider("groq", model))
        if provider == "deepseek":
            return await self._step_deepseek(
                messages, model_for_provider("deepseek", model)
            )
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

    def _build_messages_with_prompt(
        self, user_message: str, history: list[dict], system_prompt: str | None
    ) -> list[dict]:
        active_section = self._active_files_section(history)
        if system_prompt:
            prompt = system_prompt
            if active_section:
                prompt = f"{prompt}\n{active_section}"
        else:
            prompt = self._render_system_prompt(active_section)
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

            # Recovery: bazı modeller tool çağrısını metne yazıyor
            # (`<function(write_file)>{...}</function>`). Parse edip gerçek
            # tool çağrısına çeviriyoruz ki kullanıcı bozuk metin görmesin.
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
