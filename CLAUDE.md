# CLAUDE.md

Bu dosya, bu depoda çalışırken Claude Code'a (claude.ai/code) rehberlik eder.
Kullanıcıya dönük genel bilgi için **`README.md`**'ye bak.

## Proje Genel Bakış

**BSC Forge**, kişisel bir AI ürün fabrikasıdır: çok sağlayıcılı LLM sohbeti,
akıllı model yönlendirme, araç çağrısı (dosya işlemleri), ürün şablonları ve
oturum geçmişi sunan bir FastAPI backend + React/Vite frontend uygulaması.
Kod tabanı ve arayüz Türkçedir.

## Geliştirme Komutları

### Backend
```bash
source venv/bin/activate        # venv proje kökündedir
cd backend
python3 main.py                 # http://localhost:8000
```
Bağımlılıklar: `pip install -r backend/requirements.txt`

### Frontend
```bash
cd frontend
npm run dev      # http://localhost:5173 (Vite proxy: /api → :8000)
npm run build    # üretim derlemesi
```

### Hızlı API Testleri
```bash
curl http://localhost:8000/health
curl http://localhost:8000/api/models
curl -X POST http://localhost:8000/api/route \
  -H "Content-Type: application/json" \
  -d '{"message": "dosyaları listele"}'
```

### Ortam
`.env.example` → `.env` olarak kopyala ve doldur:
- `GEMINI_API_KEY` — zorunlu (birincil sağlayıcı)
- `GROQ_API_KEY` — zorunlu (yedek)
- `DEEPSEEK_API_KEY` — opsiyonel (üçüncü yedek)
- `OLLAMA_BASE_URL` — opsiyonel, varsayılan `http://localhost:11434`
- `ORCHESTRATOR_MODEL` — opsiyonel, varsayılan `llama3.2:3b` (orkestra şefi modeli)
- `MAX_AGENT_STEPS` — opsiyonel, varsayılan `5`

> **Not:** `.env` yalnızca uygulama başlangıcında okunur. Anahtar değişirse
> backend'i yeniden başlat (`python3 main.py`).

## Mimari

### İstek Akışı

```
Kullanıcı mesajı
   → WebSocket  (routers/chat.py)
   → forge_agent.run
       → model_router.route()                    (görev sınıflandırma)
       → providers.step_<gemini|groq|deepseek|ollama>
       → cascade_from() ile yedek zinciri
   → WebSocket olayları:
       token · tool · routing · model_active · fallback · approval_request · error · done
```

### Backend Modülleri

| Dosya | Görev |
|-------|-------|
| `backend/main.py` | FastAPI app, lifespan (DB başlatma), CORS, statik frontend |
| `backend/config.py` | `.env` ayarları (startup'ta yüklenir, değişmez) |
| `backend/routers/chat.py` | WebSocket + REST; `_safe_send_json` ile koruma, ping/pong |
| `backend/routers/models.py` | Model kataloğu API'si |
| `backend/routers/products.py` | Ürün CRUD |
| `backend/services/forge_agent.py` | ReAct döngüsü, cascade orkestrasyonu, write_file approval kuyruğu |
| `backend/services/agent_prompts.py` | Sistem promptu (`render_system_prompt`) |
| `backend/services/providers/` | Provider adaptörleri (gemini, groq, deepseek, ollama, base) |
| `backend/services/llm_manager.py` | Streaming (Gemini/Groq/DeepSeek/Ollama) |
| `backend/services/model_router.py` | NLP görev sınıflandırması → sağlayıcı/model seçimi |
| `backend/services/model_registry.py` | Statik bulut modelleri + dinamik Ollama keşfi |
| `backend/services/provider_utils.py` | Cascade zinciri, hata sınıflandırma, friendly errors |
| `backend/services/tools.py` | Sandbox'lı `list_directory` / `read_file` / `write_file` |
| `backend/services/chat_history.py` | Async SQLite oturum/mesaj depolama |
| `backend/services/product_store.py` | Async SQLite ürün CRUD, built-in ürünler |

### Frontend Modülleri

| Dosya | Görev |
|-------|-------|
| `frontend/src/App.jsx` | Oturum / ürün yönetimi, layout, `view` state |
| `frontend/src/components/ChatWindow.jsx` | Mesaj görüntüleme, WS akışı, markdown, approval kartları |
| `frontend/src/components/Sidebar.jsx` | Sohbet/Ürünler nav, oturum listesi |
| `frontend/src/components/ModelSelector.jsx` | Otomatik/bulut/yerel seçici |
| `frontend/src/pages/ProductsPage.jsx` | Ürün galerisi |
| `frontend/src/services/websocket.js` | Reconnect + heartbeat (ping/pong) |
| `frontend/src/services/api.js` | REST istemcisi |

### 4 Katmanlı Sağlayıcı Yedek Zinciri

`Gemini` → `Groq` → `DeepSeek` → `Ollama`

429/RESOURCE_EXHAUSTED, 502/503/504 ve `MALFORMED_FUNCTION_CALL` gibi tool format
sorunlarında otomatik geçiş. `services/provider_utils.py` algılama ve Türkçe
kullanıcı bildirimlerini yönetir.

### Model Yönlendirme

`model_router.py` görevleri kategorize eder: `file_ops`, `coding`, `turkish`,
`english`, `reasoning`, `weather`, `fast`. Arayüz, yönlendirme kararını banner
olarak gösterir. Detay: `docs/MODEL-ROUTING.md`.

### Araç Çağrısı Ajanı

`forge_agent.py` bir ReAct döngüsü çalıştırır:

1. Mesajı sınıflandır → sağlayıcı seç (cascade ile)
2. Provider'dan tool call'ları al (`providers/{gemini,groq,deepseek,ollama}.py`)
3. `write_file` çağrıları **toplu approval kuyruğuna** alınır; diğerleri hemen çalışır
4. Kullanıcı UI'da "Tümünü Kabul Et" derse `chat.py`'deki `approval_response`
   handler dosyaları yazar
5. Sandbox: `tools.resolve_path` + `is_relative_to(WORKSPACE_ROOT)` ile `..`
   ve symlink bypass'ı engellenir; `write_file` yazımdan önce TOCTOU re-check yapar

## Bilinen Sorunlar ve Kurallar

- **Türkçe dil**: Sistem istemleri, hata mesajları, arayüz etiketleri Türkçedir.
- **Üretim kilidi** (`chat.py`): React Strict Mode çift bağlantısının yinelenen
  yanıtları tetiklemesini önler.
- **Yalnızca delta akışı**: Token deltaları yayılır (birikimli metin değil); frontend her deltayı ekler.
- **Korumalı WS gönderimi**: `_safe_send_json` kopuk bağlantıya yazmayı sessizce
  yutar; ajan döngüsü bağlantı koparsa erken iptal edilir.
- **Sandbox**: `tools.py` workspace dışına çıkışı `is_relative_to()` ile engeller;
  `write_file` yazımdan önce ikinci kez doğrular (TOCTOU koruması).
- Tekrarlayan hatalar ve dersler: `docs/BILINEN-HATALAR.md`.

## Yol Haritası

Güncel durum ve fazlar: **`docs/YOL-HARITASI.md`**.
Önemli mimari değişikliklerin tarihli özeti: **`docs/DEGISIKLIK-GUNLUGU.md`**.
