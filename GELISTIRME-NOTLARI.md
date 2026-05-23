# BSC Forge — Geliştirme Notları

Bu dosya, projenin geliştirme sürecinde yapılan çalışmaları ve alınan mimari kararları belgeler.
Yeni bir geliştirici ya da yapay zeka bu dosyayı okuyarak neyin neden yapıldığını anlayabilir.

---

## Proje Amacı

**BSC Forge**, kişisel bir yapay zeka ürün fabrikasıdır.
- **Kısa vadeli hedef:** Çok sağlayıcılı (Gemini, Groq, DeepSeek, Ollama) LLM chat uygulaması; dosya okuma, akıllı model yönlendirme ve oturum geçmişi ile.
- **Uzun vadeli hedef:** Her biri farklı sistem promptu ve araç seti olan **mikro-ürünler** (English Buddy gibi) barındıran portal. İleride çok kullanıcılı olabilir.

**Stack:** Python 3.12 + FastAPI (backend) · React 19 + Vite (frontend) · SQLite (veritabanı) · WebSocket (streaming)

---

## Yapılan Çalışmalar (2026-05-23 / 24)

### 0. Başlangıç Durumu

Proje Faz 4 (~%90) tamamlanmış halde devredildi:
- Temel chat, WebSocket streaming, SQLite geçmişi çalışıyordu
- 4 katmanlı fallback zinciri (Gemini → Groq → DeepSeek → Ollama) mevcuttu
- ReAct ajan döngüsü (dosya listele / oku araçları) aktifti
- Akıllı model router NLP tabanlı görev sınıflandırması yapıyordu

---

### Aşama 1 — Altyapı Temizliği ve Güvenlik

**Neden yapıldı:** Mimari incelemede 6 kritik hata tespit edildi.

#### 1.1 `reload_env()` + `_reset_clients()` her istekte çağrılıyordu

- **Sorun:** `forge_agent.py:397` ve `llm_manager.py`'de her mesajda `.env` yeniden yükleniyor, API istemcileri sıfırlanıyordu. Thread-unsafe + gereksiz gecikme.
- **Çözüm:** Bu çağrılar kaldırıldı. Config artık yalnızca startup'ta yükleniyor. `reload_env()` fonksiyonu ve importları silindi.
- **Etki:** `config.py`, `forge_agent.py`, `llm_manager.py`

#### 1.2 `init_db()` her API isteğinde çağrılıyordu

- **Sorun:** `routers/chat.py`'deki her endpoint (`create_session`, `list_sessions`, `delete_session`) başında `await chat_history.init_db()` vardı. Zaten `main.py` lifespan'de çalışıyor olmasına rağmen.
- **Çözüm:** Router'lardaki çağrılar silindi.
- **Etki:** `routers/chat.py`

#### 1.3 DeepSeek entegrasyonu bozuktu

- **Sorun:** `llm_manager.py:174`'te `"prompt"` field kullanılıyordu. DeepSeek API, OpenAI-compat `"messages"` bekler. Streaming de desteklenmiyordu.
- **Çözüm:** Standart OpenAI-compat SSE streaming formatına geçirildi (`messages` field, `data: ...` satırları parse ediliyor).
- **Etki:** `services/llm_manager.py` → `stream_deepseek()`

#### 1.4 CORS güvenlik açığı

- **Sorun:** `allow_origins=["*"]` + `allow_credentials=True` kombinasyonu güvenlik açığı.
- **Çözüm:** `allow_origins=["http://localhost:5173", "http://localhost:3000", "http://127.0.0.1:5173"]` olarak kısıtlandı.
- **Etki:** `main.py`

#### 1.5 Symlink ile sandbox bypass riski

- **Sorun:** `tools.py`'deki `resolve_path()` fonksiyonu `..` içeren yolları engelliyor ama sembolik bağlantılarla workspace dışına çıkılabiliyordu.
- **Çözüm:** `str(target).startswith(str(workspace))` yerine Python'ın `Path.is_relative_to()` metodu kullanıldı. Sembolik bağlantılar `resolve()` sonrası gerçek yolla kontrol ediliyor.
- **Etki:** `services/tools.py` → `resolve_path()`

#### 1.6 Placeholder kontrolü kırılgandı

- **Sorun:** `is_gemini_configured()` gibi metodlar `"buraya-gemini-anahtarini-yaz"` string'ini arıyordu. Türkçe'ye özgü ve kırılgan.
- **Çözüm:** `return bool(self.GEMINI_API_KEY)` ile sadeleştirildi.
- **Etki:** `config.py`

#### 1.7 Model router yalnızca Türkçe anahtar kelimeler tanıyordu

- **Sorun:** `"list files"`, `"write code"`, `"compare"` gibi İngilizce komutlar yanlış sınıflandırılıyordu.
- **Çözüm:** `_FILE_SIGNALS`, `_CODE_SIGNALS`, `_WEATHER_SIGNALS`, `_REASONING_SIGNALS` listelerine İngilizce karşılıklar eklendi.
- **Etki:** `services/model_router.py`

---

### Aşama 2 — Frontend Güçlendirme

**Neden yapıldı:** WebSocket katmanında 5 kritik hata; uygulama çökmeleri ve kalıcı "yükleniyor" durumları.

#### 2.1 WebSocket yeniden yazıldı

**Eski durum:**
- JSON parse'da try-catch yoktu → hatalı veri = uygulama çöküyor
- Bağlantı kopunca yeniden bağlanma yoktu → kullanıcı sayfayı yenilemek zorunda
- Heartbeat yoktu → proxy arkasında ölü bağlantı tespit edilemiyordu

**Yeni `websocket.js`:**
- JSON parse try-catch + hata mesajı
- Exponential backoff reconnect: 1s → 2s → 4s → 8s → 16s → max 30s (5 deneme)
- 30 saniyede bir ping gönderir; backend `{"type":"pong"}` ile yanıt verir
- `onDisconnect` callback: bağlantı kopunca `isStreaming` zorla sıfırlanır
- `session_id` guard: oturum yoksa hata mesajı gösterilir, mesaj gönderilmez

**Backend'e eklenen:**
```python
# routers/chat.py — WebSocket döngüsünde
if data.get("type") == "ping":
    await websocket.send_json({"type": "pong"})
    continue
```

#### 2.2 Mesajlara unique ID eklendi

- **Sorun:** `messages.map((msg, index) => <div key={index}>` — React'ın index key anti-pattern'i; mesajlar yeniden sıralanırsa render hataları çıkar.
- **Çözüm:** `genId()` fonksiyonu (`Date.now() + Math.random()`) ile her yeni mesaja benzersiz `id` üretiliyor. API'den yüklenen mesajlar için `created_at + index` kullanılıyor.
- **Etki:** `ChatWindow.jsx`, `App.jsx`

#### 2.3 Hata callback düzeltildi

- **Sorun:** `opened` flag kontrolü nedeniyle WebSocket bağlantı hatası callback'i hiç tetiklenmiyordu.
- **Çözüm:** `opened` flag kaldırıldı; hatalar her zaman kullanıcıya gösterilir.

#### 2.4 Model listesi boşsa UI sessizce kapanmıyordu

- **Çözüm:** Model yüklenemezse header'da "⚠ Model listesi yüklenemedi" uyarısı gösterilir.

---

### Aşama 3 — Ürün Mimarisi

**Neden yapıldı:** Projenin uzun vadeli hedefi olan "mikro-ürün fabrikası" kavramını mimariye yansıtmak.

#### "Ürün" nedir?

Bir ürün, özelleştirilmiş bir chat konfigürasyonudur:
```python
class Product:
    id: str                  # "forge", "english_buddy"
    name: str                # "English Buddy"
    description: str
    icon: str                # emoji
    system_prompt: str|None  # None ise Forge varsayılanı kullanılır
    tools_enabled: list[str] # ["read_file", "list_directory"] veya []
    preferred_provider: str  # "auto", "gemini", "groq"
    preferred_model: str
    is_builtin: bool
```

Kullanıcı bir ürünle session başlattığında → normal session oluşturulur, ama `system_prompt` ve `tools_enabled` o ürünün konfigürasyonundan gelir.

#### Eklenen bileşenler

**Backend:**
- `services/product_store.py` — SQLite `products` tablosu, CRUD, startup'ta yerleşik ürünleri ekle
- `routers/products.py` — `GET /api/products`, `GET /api/products/{id}`, `POST /api/products`, `DELETE /api/products/{id}`
- `main.py` → `product_store.init_table()` lifespan'e eklendi
- `forge_agent.run()` → `system_prompt: str | None` ve `tools_enabled: list[str] | None` parametreleri eklendi
- `routers/chat.py` → WebSocket'ten gelen `product_id` ile ürün konfigürasyonu yükleniyor, ajan'a geçiriliyor

**Frontend:**
- `pages/ProductsPage.jsx` — ürün galeri sayfası; kart görünümü, yeni ürün formu, silme
- `services/api.js` → `fetchProducts`, `createProduct`, `deleteProduct` fonksiyonları
- `Sidebar.jsx` → "Sohbet / Ürünler" navigasyon sekmeleri (`LayoutGrid` ikonu)
- `App.jsx` → `view` state (`'chat'` | `'products'`), `handleStartProduct()`, `activeProductId` state
- `index.css` → ürün kartları, form, sidebar nav için stiller

**Yerleşik ürünler (otomatik oluşturuluyor):**

| ID | Ad | Araçlar | Provider |
|----|----|---------|----------|
| `forge` | Forge Ajan | `list_directory`, `read_file` | auto |
| `english_buddy` | English Buddy | — | Gemini |

English Buddy'nin özel sistem promptu İngilizce öğretime göre ayarlanmış; hataları nazikçe düzeltiyor, seviyeye göre konuşuyor.

---

## Mimari Genel Bakış

```
backend/
├── main.py                    # FastAPI app, lifespan (DB init)
├── config.py                  # Startup'ta yüklenir, değişmez
├── routers/
│   ├── chat.py                # WebSocket + session REST, ping/pong
│   ├── models.py              # Model kataloğu API
│   └── products.py            # Ürün CRUD
└── services/
    ├── forge_agent.py         # ReAct ajan; system_prompt + tools_enabled destekler
    ├── llm_manager.py         # Gemini/Groq/DeepSeek/Ollama streaming
    ├── model_router.py        # NLP görev sınıflandırması → provider seçimi
    ├── model_registry.py      # Model kataloğu, Ollama keşfi
    ├── provider_utils.py      # Fallback zinciri, hata sınıflandırması
    ├── tools.py               # Sandboxed list_directory + read_file
    ├── chat_history.py        # SQLite session/message CRUD
    └── product_store.py       # SQLite product CRUD, yerleşik ürünler

frontend/src/
├── App.jsx                    # view state, session/product yönetimi
├── pages/
│   └── ProductsPage.jsx       # Ürün galerisi
├── components/
│   ├── ChatWindow.jsx         # Streaming chat, WebSocket lifecycle
│   ├── Sidebar.jsx            # Nav sekmeleri + session listesi
│   └── ModelSelector.jsx      # Model seçici dropdown
└── services/
    ├── websocket.js           # Reconnect + heartbeat + ping/pong
    └── api.js                 # REST istemcisi
```

## Çalıştırma

```bash
# Backend
cd backend && source venv/bin/activate && python3 main.py

# Frontend (ayrı terminal)
cd frontend && npm run dev
```

Frontend: http://localhost:5173 · Backend: http://localhost:8000

### Aşama 4 — write_file Aracı Tamamlandı (2026-05-24)

`write_file` aracı onay mekanizmasıyla tam olarak çalışıyor. Yapılan düzeltmeler:

1. **`product_store.py`** — `forge` ürününün `tools_enabled` listesine `write_file` eklendi.
   `INSERT OR IGNORE` → `INSERT OR REPLACE` değiştirildi; böylece built-in ürün tanımları her başlatmada güncellenir.

2. **`forge_agent.py`** — Sistem prompt'una `write_file` tanımı eklendi. Ayrıca `seen.add(key)` çift çağrı bug'ı düzeltildi.

3. **`services/tools.py`** — `write_file` fonksiyonu ve schema'sı (önceki aşamada eklenmiş).

4. **`routers/chat.py`** — `approval_response` handler (önceki aşamada eklenmiş).

5. **`frontend/ChatWindow.jsx`** — Onay kartı UI + `handleApproval` (önceki aşamada eklenmiş).

**Akış:**
```
Kullanıcı: "merhaba.html oluştur"
  → Agent Gemini/Groq'tan write_file tool call alır
  → approval_request event yield edilir, agent durur
  → Frontend: onay kartı gösterilir (dosya yolu + içerik önizlemesi)
  → Kullanıcı "Onayla" tıklar
  → approval_response WS'e gönderilir
  → Backend write_file çalıştırır, ✅ mesajı döner
  → Kullanıcı "Reddet" tıklarsa: ❌ mesajı döner, dosya yazılmaz
```

**Test sonuçları:**
- `approval_request` olayı: ✅ alınıyor
- Onay sonrası dosya oluşturma: ✅ çalışıyor
- Reddetme akışı: ✅ çalışıyor

---

## Kalan İşler (Gelecek Fazlar)

- **Faz 4 tamamlama:** Kod çalıştırma sandbox'ı, web arama aracı
- **Faz 5:** English Buddy'yi tam özellikli hale getir (seviye seçimi, ilerleyiş takibi)
- **Faz 6:** QLoRA fine-tuning UI, GGUF dışa aktarma
- **Teknik borç:** Yapılandırılmış loglama, veritabanı migration sistemi, unit testler, Context API ile frontend state yönetimi
