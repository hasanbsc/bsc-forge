# 🏛️ BSC Forge — Mimari

> Kod tabanının iç işleyişi: katmanlar, sorumluluklar ve istek akışı.

---

## Üst Seviye

```
┌──────────────────────┐         ┌──────────────────────────┐
│   Frontend (Vite)    │  WS +   │     Backend (FastAPI)    │
│   React 19           │  REST   │  ┌────────────────────┐  │
│  ChatWindow.jsx      ├────────►│  │  routers/chat.py    │  │
│  Sidebar.jsx         │         │  └─────────┬──────────┘  │
│  ProductsPage.jsx    │         │            ▼              │
└──────────────────────┘         │  ┌────────────────────┐  │
                                  │  │ services/           │  │
                                  │  │  forge_agent.py     │  │
                                  │  │  ├ model_router     │  │
                                  │  │  ├ providers/       │  │
                                  │  │  └ tools.py         │  │
                                  │  └─────────┬──────────┘  │
                                  │            ▼              │
                                  │  ┌────────────────────┐  │
                                  │  │ LLM Sağlayıcıları   │  │
                                  │  │ Gemini · Groq ·     │  │
                                  │  │ DeepSeek · Ollama   │  │
                                  │  └────────────────────┘  │
                                  └──────────────────────────┘
```

---

## İstek Akışı (Bir Sohbet Mesajı)

```
1. Kullanıcı mesaj yazar
   └─ Frontend: ChatWindow.jsx → websocket.js.send()

2. WebSocket alır
   └─ routers/chat.py: chat_websocket
       ├─ ping/pong / approval_response gibi özel mesajları işle
       ├─ product_store.get_product(product_id)        → sistem promptu + araç seti
       ├─ model_router.route(message)                   → görev → sağlayıcı/model
       └─ forge_agent.run(...)                          → async generator

3. forge_agent.run ReAct döngüsü (en fazla MAX_AGENT_STEPS)
   ├─ Her adımda _step_with_cascade(provider)
   │   ├─ cascade_from(start) → ['gemini','groq','deepseek','ollama']
   │   └─ İlk başarılı sağlayıcının step_*() çağrısı:
   │       ├─ providers/gemini.py    → step_gemini
   │       ├─ providers/groq.py      → step_groq
   │       ├─ providers/deepseek.py  → step_deepseek
   │       └─ providers/ollama.py    → step_ollama (heuristic)
   ├─ StepResult.tool_calls boş değilse:
   │   ├─ list_directory / read_file → tools.execute_tool, geçmişe ekle
   │   └─ write_file → batch'e topla, approval_request event yay, dur
   └─ tools_used ise ve sadece list_directory yapıldıysa:
       └─ _local_tool_summary (ek API çağrısı yok, kota tasarrufu)

4. Her yield edilen event WebSocket'e gönderilir
   └─ _safe_send_json → bağlantı koparsa sessizce False döner
       └─ forge_agent erken iptal

5. Akış tamamlanınca
   └─ done eventi + sessions'a assistant mesajı kaydı
```

---

## Modül Sorumlulukları

### `backend/main.py`
- FastAPI app, CORS, statik frontend mount, router'ları bağlar.
- `lifespan` içinde `chat_history.init_db()` + `product_store.init_table()`.

### `backend/config.py`
- `.env` dosyasını **yalnızca startup'ta** yükler.
- API anahtarları, workspace kökü, `MAX_AGENT_STEPS`, varsayılan model.
- `is_*_configured()` metodları boolean.

### `backend/routers/`
| Dosya | Endpoint'ler |
|-------|--------------|
| `chat.py` | `/sessions` CRUD + `/ws` WebSocket. `_safe_send_json` koruması, `approval_response` handler, ping/pong. |
| `models.py` | `/api/models` — bulut + Ollama dinamik katalog. `/api/route` — yönlendirme kararı testi. |
| `products.py` | `/api/products` CRUD. |

### `backend/services/`

#### Ajan Çekirdeği
| Dosya | Ne yapar? |
|-------|-----------|
| `forge_agent.py` | ReAct döngüsü, cascade orkestrasyonu, write_file batch approval, yerel matematik, aktif dosya izleme. |
| `agent_prompts.py` | Sistem promptu metni + `render_system_prompt(workspace, active_files_section)`. |
| `providers/base.py` | `ToolCall`, `StepResult` veri tipleri. |
| `providers/gemini.py` | Gemini tool-calling adımı; `MALFORMED_FUNCTION_CALL`/`MAX_TOKENS` durumunda exception fırlatıp cascade'i tetikler. |
| `providers/groq.py` | Groq tool-calling + `groq_tools_schema()` (OpenAI-uyumlu). |
| `providers/deepseek.py` | DeepSeek HTTP API üzerinden OpenAI-uyumlu tool-calling. |
| `providers/ollama.py` | Ollama tool API'si yok; sezgisel (keyword) tool çağrıları üretir. |

#### Provider Yardımcıları
| Dosya | Ne yapar? |
|-------|-----------|
| `llm_manager.py` | Streaming yanıtları (Gemini/Groq/DeepSeek/Ollama). `stream_with_notices`. |
| `model_router.py` | NLP görev sınıflandırması → `RouteDecision`. |
| `model_registry.py` | Statik bulut model kataloğu + dinamik Ollama keşfi. |
| `provider_utils.py` | `cascade_from`, `is_fallbackable_error`, `friendly_provider_error`, `model_active_event`. |

#### Veri & Araçlar
| Dosya | Ne yapar? |
|-------|-----------|
| `tools.py` | Sandbox'lı `list_directory` / `read_file` / `write_file`. Path traversal + symlink + TOCTOU koruması. |
| `chat_history.py` | Async SQLite oturum/mesaj depolama. |
| `product_store.py` | Async SQLite ürün CRUD; built-in ürünleri startup'ta `INSERT OR REPLACE` ile günceller. |

### `frontend/src/`
| Dosya | Ne yapar? |
|-------|-----------|
| `App.jsx` | `view` state (chat / products), oturum + ürün yönetimi. |
| `components/ChatWindow.jsx` | Mesaj görüntüleme, WS akışı, markdown render, approval kartları. |
| `components/Sidebar.jsx` | Sohbet/Ürünler nav, oturum listesi. |
| `components/ModelSelector.jsx` | Otomatik/bulut/yerel seçici (Lucide ikonları). |
| `pages/ProductsPage.jsx` | Ürün galerisi (kart UI, yeni ürün formu). |
| `services/websocket.js` | `ChatWebSocket` — reconnect (1s→30s, 5 deneme), 30s heartbeat. |
| `services/api.js` | REST istemcisi (sessions, models, products). |

---

## WebSocket Olayları (Sunucu → İstemci)

| Tip | Yayan | Anlamı |
|-----|--------|--------|
| `model_active` | router seçim | Şu an hangi model yanıtlıyor (badge için) |
| `routing` | otomatik mod | Yönlendirme kararı + açıklama |
| `tool` | ajan | Bir araç çağrılıyor (📂 / 📄 / ✏️) |
| `approval_request` | ajan | `write_file` için kullanıcı onayı bekleniyor |
| `fallback` | cascade | Bir sağlayıcı düştü, sonrakine geçiliyor |
| `token` | streaming | Yanıt deltası (birikimli değil) |
| `error` | her yer | Türkçe hata mesajı |
| `done` | tamamlandı | Akış bitti; `usage` (in/out token ~) içerir |
| `pong` | ping yanıtı | Heartbeat |

## WebSocket Olayları (İstemci → Sunucu)

| Tip | Anlamı |
|-----|--------|
| `(default)` | Yeni kullanıcı mesajı: `{message, session_id, provider, model, history, product_id}` |
| `ping` | Heartbeat |
| `approval_response` | `{approved, path, folder, session_id}` — write_file onayı/reddi |

---

## 4 Katmanlı Fallback Zinciri

```
   ┌─────────┐    429/5xx     ┌─────────┐   429/5xx   ┌──────────┐   herhangi   ┌─────────┐
   │ Gemini  │───────────────►│  Groq   │────────────►│ DeepSeek │─────────────►│ Ollama  │
   │  Flash  │  MALFORMED_FC  │ Llama70 │   capacity  │   chat   │              │  yerel  │
   └─────────┘    MAX_TOKENS  └─────────┘             └──────────┘              └─────────┘
```

`services/provider_utils.py:is_fallbackable_error` aşağıdakileri yakalar ve
zinciri ilerletir:
- Kota / rate limit: `429`, `402`, `RESOURCE_EXHAUSTED`, `quota`, `rate limit`,
  `too many requests`, `insufficient balance`, `capacity`
- Sunucu: `502`, `503`, `504`, `unavailable`, `overloaded`
- Tool format: `tool_use_failed`, `malformed function call`, `max_tokens`

---

## Sandbox Güvenliği (tools.py)

1. **Path traversal**: `..` içeren parçalar reddedilir.
2. **Symlink bypass**: `target.resolve().is_relative_to(workspace)` ile gerçek
   yol kontrol edilir.
3. **TOCTOU**: `write_file`'da `mkdir`'den sonra ikinci `is_relative_to()`
   kontrolü — parent path symlink'lenirse yazma reddedilir.
4. **Boyut sınırı**: okuma 80KB, yazma 200KB üstü reddedilir.
5. **Onay**: `write_file` doğrudan çalışmaz — `approval_request` event'i ile
   kullanıcı onayı beklenir.

---

## Konfigürasyon Notları

- `.env` **yalnızca uygulama başlangıcında** okunur. Anahtar değişiklikleri
  için backend yeniden başlatılmalı.
- `MAX_AGENT_STEPS=5` varsayılan; env ile override edilebilir.
- CORS yalnızca `localhost:5173`, `localhost:3000` ve 127.0.0.1 eşdeğerleri.
  Production'da bu liste güncellenmeli.
