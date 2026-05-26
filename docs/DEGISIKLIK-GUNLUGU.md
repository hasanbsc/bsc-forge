# 📝 BSC Forge — Değişiklik Günlüğü

> Mimari kararlar ve önemli değişiklikler (tarih sırasıyla, en yeni üstte).
> Küçük bug fix'ler buraya girmez — onlar git log'da.

---

## 2026-05-26 — Üyelik Sistemi (Faz 7.1)

### Yeni özellikler
- **E-posta + şifre tabanlı üyelik** (`services/auth.py`, `routers/auth.py`)
  - `bcrypt` ile şifre hash, `PyJWT` ile HS256 token (7 gün ömür)
  - Endpoint'ler: `POST /api/auth/register`, `POST /api/auth/login`,
    `GET /api/auth/me`, `POST /api/auth/claim-anonymous`
  - `JWT_SECRET` `.env`'den okunur; yoksa rastgele üretilir ve uyarı loglanır
- **Anonim → üye geçiş akışı**
  - Her tarayıcıya kalıcı bir `browser_id` (localStorage) atanır
  - Anonim sohbetler `sessions.browser_id` ile işaretlenir; üye olunca
    `claim_anonymous_sessions` ile `user_id`'ye bağlanır
  - REST'te `X-Browser-Id` header'ı; WS'te `?token=...&browser_id=...`
  - Yetki kontrolü: REST + WS'te `_can_access` / `_ws_can_use_session`
- **Frontend**
  - `services/auth.js` — token + browser_id yönetimi, tüm REST/WS isteklerinde
    otomatik header ekleme
  - `components/AuthModal.jsx` — giriş/kayıt toggle'lı modal
  - Sidebar'da kullanıcı widget'ı / "Giriş Yap" butonu
  - `App.jsx`: `authVersion` ile WS kimlik değişiminde otomatik reconnect

### Şema migrasyonu (idempotent)
- `sessions` tablosuna `user_id TEXT NULL` ve `browser_id TEXT NULL` sütunları
  + index'leri eklendi (`_migrate_sessions_user_columns`).
- Yeni tablo: `users(id, email UNIQUE, password_hash, created_at)`.

### Notlar
- Şifre kurtarma / e-posta doğrulama kapsam dışı (magic link gerekir).
- Refresh token yok; basit single-token modeli.

---

## 2026-05-25 — Mimari Temizlik

### Kritik düzeltmeler
- **CORS sıkılaştırma** (`backend/main.py`)
  Önceki `allow_origins=["*"]` + `allow_credentials=True` kombinasyonu güvensizdi.
  Şimdi `localhost:5173`, `localhost:3000` ve 127.0.0.1 eşdeğerleriyle sınırlı.
- **WebSocket exception handler** (`routers/chat.py`)
  Daha önce tüm exception'lar sessizce yutuluyordu. Şimdi `_safe_send_json`
  ile her gönderim koruma altında; ajan akışı bağlantı koparsa erken iptal
  edilir; üst seviye exception'lar `logger.exception` ile loglanır ve
  kullanıcıya Türkçe hata gönderilir.
- **`write_file` TOCTOU re-check** (`services/tools.py`)
  `resolve_path` → `mkdir` → `write_text` zincirinde parent path
  symlink'lenirse workspace dışına yazma mümkündü. Yazımdan hemen önce
  ikinci `is_relative_to()` kontrolü eklendi.
- **`MAX_AGENT_STEPS`** artık `config.py`'de (env değişkeniyle override
  edilebilir).

### Refaktör
- **`forge_agent.py` 900 → 475 satır** (~%47 azaltma)
  - Sistem promptu (~200 satır) → `services/agent_prompts.py`
  - 4 provider step fonksiyonu → `services/providers/`:
    - `providers/base.py` — `ToolCall`, `StepResult`
    - `providers/gemini.py` — `step_gemini`
    - `providers/groq.py` — `step_groq` + `groq_tools_schema` (DeepSeek de bunu kullanır)
    - `providers/deepseek.py` — `step_deepseek`
    - `providers/ollama.py` — `step_ollama` + `heuristic_tool_calls`
  - `forge_agent.py` artık yalnızca orkestrasyon (cascade, ReAct döngüsü,
    write_file approval kuyruğu, yerel matematik, aktif dosya izleme)

### Dokümantasyon
- `README.md` eklendi (Faz 1 kalan görevi).
- `CLAUDE.md` güncel kodla hizalandı — `reload_env()` / `_reset_clients()`
  referansları kaldırıldı (bunlar zaten 05-23'te silinmişti).
- `PLAN.md` + `status.md` → tek `docs/YOL-HARITASI.md` halinde birleştirildi.
- `GELISTIRME-NOTLARI.md` → bu `docs/DEGISIKLIK-GUNLUGU.md` halinde özetlendi.
- Yeni `docs/MIMARI.md` — sınıf/dosya sorumlulukları ve akış diyagramı.

---

## 2026-05-24 — Codex Tarzı Kodlama + Ürün Mimarisi

### Çoklu dosya akışı
- Sistem promptuna **paralel `write_file` çağırma zorunluluğu** eklendi.
  Modelin tek yanıtta birden fazla function call üretmesi şart.
- Frontend'de **batch approval kuyruğu** — "Tümünü Kabul Et" butonu.
- Aktif dosya izleme: `_WRITE_TRACE_PATTERN` ile geçmişten son yazılan
  dosyalar çıkarılır; düzenleme isteklerinde yeni dosya açmak yerine
  aynı yol yeniden kullanılır.

### Ürün katmanı (mikro-ürün fabrikası temeli)
Bir ürün = özelleştirilmiş chat konfigürasyonu (sistem promptu + araç seti
+ tercih edilen sağlayıcı).
- `services/product_store.py` — async SQLite `products` tablosu, CRUD,
  startup'ta built-in ürünleri kurar (`INSERT OR REPLACE`).
- `routers/products.py` — `GET/POST/DELETE /api/products`.
- `forge_agent.run()` artık `system_prompt` ve `tools_enabled` parametrelerini
  destekler.
- Frontend: `ProductsPage.jsx` kart galeri, sidebar nav sekmesi.

### `write_file` aracı tamamlandı
- `forge` ürününün `tools_enabled` listesine eklendi.
- Sistem promptuna araç tanımı eklendi.
- Approval akışı: tool call → `approval_request` event → UI kartı →
  `approval_response` → backend `write_file` → `✅`/`❌` mesajı.

---

## 2026-05-23 — Güvenlik ve DeepSeek

### Altyapı temizliği (6 kritik hata)
1. `reload_env()` + `_reset_clients()` her istekte çağrılıyordu — kaldırıldı.
   Config artık yalnızca startup'ta yüklenir; anahtar değiştiğinde backend
   yeniden başlatılmalı.
2. `init_db()` her API isteğinde çağrılıyordu — router'lardan kaldırıldı
   (zaten lifespan'da çalışıyor).
3. **DeepSeek entegrasyonu bozuktu** — `"prompt"` field yerine OpenAI-uyumlu
   `"messages"` ve SSE streaming yapıldı.
4. **CORS** `allow_origins=["*"]` + `allow_credentials=True` → localhost
   origin'leriyle sınırlandırıldı. (Bu güncellemenin tam kodu 05-25'te tamamlandı.)
5. **Symlink sandbox bypass** — `tools.resolve_path` artık
   `Path.is_relative_to()` kullanıyor.
6. **Placeholder kontrolü** — `is_*_configured()` metodları `bool(KEY)` ile
   sadeleştirildi.

### Akıllı router + 4 katmanlı zincir
- `services/model_router.py` — NLP görev sınıflandırması; İngilizce
  anahtar kelimeler de eklendi.
- `services/model_registry.py` — görev etiketleri (file_ops, coding,
  turkish, english, reasoning, weather, fast), öncelik sistemi, Ollama
  dinamik katalog.
- `services/provider_utils.py` — fallback zinciri, hata sınıflandırma
  (`is_quota_or_rate_limit`, `is_fallbackable_error`, `is_auth_error`,
  `friendly_provider_error`), `model_active_event`.
- WebSocket olayları: `routing`, `model_active`, `fallback`.

### Frontend güçlendirme (5 hata)
- WebSocket yeniden yazıldı: JSON parse try-catch, exponential backoff
  reconnect (1s → 30s, 5 deneme), 30s heartbeat (ping/pong), `onDisconnect`
  callback `isStreaming`'i sıfırlar.
- Mesajlara `genId()` ile unique ID — `index` key anti-pattern'i bitti.
- Bağlantı hatası callback'i her zaman tetiklenir (eski `opened` flag kaldırıldı).
- Model listesi yüklenemezse header'da uyarı.

---

## 2026-05-22 — Forge Ajan v1

- Tool-calling iskeleti: `services/tools.py` (`list_directory`, `read_file`),
  `services/forge_agent.py` (ReAct döngüsü), WebSocket `tool` + `token` olayları.
- 3 katmanlı fallback (Gemini → Groq → Ollama) — DeepSeek 05-23'te eklendi.
- Çoklu Ollama: `ollama list` ile yüklü modeller otomatik kataloga eklenir.
- UI'da "Otomatik (Akıllı)" seçeneği.

---

## 2026-05-22 (öğleden sonra) — Faz 1 Kapanışı

- `init_db` lifespan'a eklendi → yeni sohbet düzeldi.
- Sohbet silme: sidebar UI + REST `DELETE /sessions/{id}`.
- Gemini ile uçtan uca WebSocket testi başarılı.
- `.gitignore` Python testing/cache dosyalarıyla güncellendi.

---

## 2026-05-22 (sabah) — Başlangıç

- Proje planı oluşturuldu; donanım analizi (i7-7700HQ, 16GB RAM, GPU yok).
- Hibrit model stratejisi: bulut API (Gemini/Groq) + CPU yerel (Ollama).
- Proje ismi: **BSC Forge**.
- Faz 1 geliştirmesi başladı.
