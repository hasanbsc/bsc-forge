# CLAUDE.md

Bu dosya, bu depoda çalışırken Claude Code'a (claude.ai/code) rehberlik etmek amacıyla hazırlanmıştır.

## Proje Genel Bakış

**BSC Forge**, kişisel bir AI ürün fabrikasıdır: çok sağlayıcılı LLM sohbeti, akıllı model yönlendirme, araç çağrısı (dosya işlemleri) ve oturum geçmişi sunan bir FastAPI backend + React/Vite frontend uygulaması. Kod tabanı ve arayüz büyük ölçüde Türkçedir.

## Geliştirme Komutları

### Backend

```bash
cd backend
source venv/bin/activate        # sanal ortamı etkinleştir
python3 main.py                 # http://localhost:8000 üzerinde başlat
```

Bağımlılıkları yükle: `pip install -r backend/requirements.txt`

### Frontend

```bash
cd frontend
npm run dev      # http://localhost:5173 üzerinde başlat (/api → :8000 proxy)
npm run build    # üretim derlemesi
```

### Hızlı API Testleri

```bash
curl http://localhost:8000/                    # sağlık kontrolü
curl http://localhost:8000/api/models          # mevcut modelleri listele
curl -X POST http://localhost:8000/api/route \
  -H "Content-Type: application/json" \
  -d '{"message": "dosyaları listele"}'        # model yönlendirmeyi test et
```

### Ortam Kurulumu

`.env.example` dosyasını `.env` olarak kopyala ve şunları ekle:
- `GEMINI_API_KEY` — zorunlu (birincil sağlayıcı)
- `GROQ_API_KEY` — zorunlu (yedek)
- `DEEPSEEK_API_KEY` — isteğe bağlı (üçüncü yedek)
- `OLLAMA_BASE_URL` — varsayılan `http://localhost:11434` (son yedek)

`config.py` her istekte `.env` dosyasını yeniden yüklediğinden, anahtar değişiklikleri yeniden başlatma gerektirmez.

## Mimari

### İstek Akışı

Kullanıcı mesajı → WebSocket (`routers/chat.py`) → `forge_agent.py` → `model_router.py` görevi sınıflandırır → sağlayıcı/model seçilir → token'lar şu olay tipleriyle akıtılır: `token`, `tool`, `routing`, `model_active`, `fallback`, `error`, `done`

### Temel Backend Servisleri

| Dosya | Görev |
|-------|-------|
| `backend/main.py` | FastAPI uygulaması, lifespan (DB başlatma), CORS |
| `backend/config.py` | `.env` ayarları; her istekte `reload_env()` + `_reset_clients()` |
| `backend/routers/chat.py` | WebSocket + REST uç noktaları; üretim kilidi tekrarları önler |
| `backend/routers/models.py` | Model kataloğu API'si |
| `backend/services/forge_agent.py` | ReAct tarzı araç çağrısı döngüsü |
| `backend/services/llm_manager.py` | Çok sağlayıcılı akış (Gemini/Groq/DeepSeek/Ollama) |
| `backend/services/model_router.py` | NLP görev sınıflandırması → sağlayıcı/model seçimi |
| `backend/services/model_registry.py` | Statik bulut modelleri + dinamik Ollama model keşfi |
| `backend/services/provider_utils.py` | 4 katmanlı yedek zinciri; 429/kota hatalarını algılar |
| `backend/services/tools.py` | Korumalı alan dosya işlemleri (`list_directory`, `read_file`); 80KB sınırı |
| `backend/services/chat_history.py` | Asenkron SQLite oturum/mesaj depolama (`data/chat_history.db`) |

### 4 Katmanlı Sağlayıcı Yedek Zinciri

Gemini (birincil, ücretsiz ~20 istek/gün) → Groq (hızlı, yüksek kota) → DeepSeek → Ollama (yerel, sınırsız). 429/RESOURCE_EXHAUSTED hatalarında otomatik devreye girer. `provider_utils.py` algılama ve kullanıcıya Türkçe bildirimleri yönetir.

### Model Yönlendirme

`model_router.py` görevleri şu kategorilere ayırır: `file_ops`, `coding`, `turkish`, `english`, `reasoning`, `weather`, `fast`. Her görev tipi tercih edilen sağlayıcı/modele eşlenir. Arayüz yönlendirme kararını banner olarak gösterir (örn. "Görev: Dosya / proje → Gemini 2.5 Flash").

### Araç Çağrısı Ajanı

`forge_agent.py` bir ReAct döngüsü çalıştırır: görevi sınıflandır → araçları çağır → sonuçları işle → yanıtı akıt. Dosya araçları proje köküyle sınırlıdır (`..` geçişine izin verilmez). Gemini ve Groq yerel araç çağrısı API'lerini destekler; Ollama için sezgisel yedek mevcuttur.

### Frontend

| Dosya | Görev |
|-------|-------|
| `frontend/src/App.jsx` | Oturum yönetimi, kenar çubuğu/sohbet düzeni |
| `frontend/src/components/ChatWindow.jsx` | Mesaj görüntüleme, WebSocket akışı, markdown render |
| `frontend/src/components/Sidebar.jsx` | Oturum listesi, model seçici |
| `frontend/src/components/ModelSelector.jsx` | Açılır menü: Otomatik/bulut/yerel, Lucide ikonları |
| `frontend/src/services/websocket.js` | `ChatWebSocket` sınıfı; token akışını yönetir |
| `frontend/src/services/api.js` | Oturumlar ve modeller için REST istemcisi |

Vite, geliştirme modunda `/api/*` isteklerini `http://localhost:8000` adresine yönlendirir (`vite.config.js`).

## Bilinen Sorunlar ve Kurallar

- **Türkçe dil**: Sistem istemleri, hata mesajları, arayüz etiketleri ve satır içi belgeler Türkçedir.
- **Üretim kilidi** (`chat.py`): React Strict Mode çift bağlantısının yinelenen yanıtları tetiklemesini önler.
- **Yalnızca delta akışı**: Akış birikimli metin değil, token deltalarını yayar — frontend her deltayı ekler.
- **API anahtarı güncelliği**: `config.py`, istek zamanında `reload_env()` + `_reset_clients()` çağırır; `.env` düzenlemeleri yeniden başlatma gerektirmeden geçerli olur.
- Belgelenmiş geçmiş hatalar ve düzeltmeler için `docs/BILINEN-HATALAR.md` dosyasına bakın.

## Proje Yol Haritası

`PLAN.md` ve `status.md` dosyalarında takip edilmektedir. Mevcut aşama: **Faz 4** (~%90 tamamlandı) — dosya araçları, akıllı yönlendirici ve 4 katmanlı yedek zinciriyle Forge Ajanı. Sonraki: Faz 5 (English Buddy ürünü), Faz 6 (QLoRA ince ayarı).
