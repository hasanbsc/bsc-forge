# 🔨 BSC Forge

> Kişisel yapay zeka ürün fabrikası — birden çok LLM sağlayıcısını, akıllı yönlendirmeyi ve dosya araçlarını tek bir arayüzde birleştirir.

---

## Nedir?

**BSC Forge**, çok sağlayıcılı (Gemini, Groq, DeepSeek, yerel Ollama) bir LLM
sohbet uygulamasıdır. Sıradan bir chat arayüzünün üstünde şunlar var:

- **Akıllı model yönlendirme** — mesajı sınıflandırıp en uygun modeli seçer
- **4 katmanlı yedek zinciri** — bir sağlayıcı düşerse otomatik sonrakine geçer
- **Dosya araçları** — onay mekanizmalı `read_file` / `write_file` / `list_directory`
- **Ürünler** — farklı sistem promptu ve araç setiyle özelleştirilmiş "mikro asistanlar"
- **Oturum geçmişi** — SQLite tabanlı kalıcı sohbetler

Arayüz Türkçedir.

---

## Hızlı Başlangıç

### 1. Ön Koşullar
- Python 3.11+
- Node.js 18+
- (Opsiyonel) Ollama — yerel modeller için: `https://ollama.com`

### 2. API Anahtarları
`.env.example` dosyasını `.env` olarak kopyala ve doldur:

```bash
cp .env.example .env
```

Anahtarları al:
- **Gemini** (zorunlu, ücretsiz ~20 istek/gün) → https://aistudio.google.com/apikey
- **Groq** (zorunlu, hızlı + yüksek kota) → https://console.groq.com/keys
- **DeepSeek** (opsiyonel) → https://platform.deepseek.com
- **Ollama** (opsiyonel, yerel) → `OLLAMA_BASE_URL` varsayılan `http://localhost:11434`

### 3. Backend
```bash
cd backend
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
python3 main.py            # http://localhost:8000
```

### 4. Frontend (ayrı terminal)
```bash
cd frontend
npm install
npm run dev                # http://localhost:5173
```

Vite, geliştirme modunda `/api/*` isteklerini backend'e yönlendirir.

---

## Hızlı Test

```bash
curl http://localhost:8000/health                    # sağlık kontrolü
curl http://localhost:8000/api/models                # model listesi
curl -X POST http://localhost:8000/api/route \
  -H "Content-Type: application/json" \
  -d '{"message": "backend dosyalarını listele"}'    # router kararı
```

---

## Proje Yapısı

```
bsc-forge/
├── backend/                  # FastAPI + WebSocket
│   ├── main.py               # uygulama girişi, lifespan
│   ├── config.py             # .env'den ayarlar
│   ├── routers/              # chat, models, products endpoint'leri
│   └── services/
│       ├── forge_agent.py    # ReAct ajan döngüsü
│       ├── agent_prompts.py  # sistem promptu
│       ├── providers/        # Gemini / Groq / DeepSeek / Ollama adaptörleri
│       ├── llm_manager.py    # streaming
│       ├── model_router.py   # NLP görev sınıflandırma
│       ├── tools.py          # sandbox'lı dosya araçları
│       └── chat_history.py   # SQLite oturum / mesaj
├── frontend/                 # React 19 + Vite
└── docs/
    ├── MIMARI.md             # mimari ve istek akışı
    ├── YOL-HARITASI.md       # fazlar ve durum
    ├── DEGISIKLIK-GUNLUGU.md # tarihli değişiklikler
    ├── BILINEN-HATALAR.md    # tekrar etmemek için dersler
    └── MODEL-ROUTING.md      # akıllı yönlendirme tasarımı
```

`CLAUDE.md` Claude Code için rehberdir — kod yazılırken otomatik yüklenir.

---

## Dokümantasyon

| Belge | İçerik |
|------|--------|
| [docs/MIMARI.md](docs/MIMARI.md) | Mimari diyagram, istek akışı, sınıf/dosya sorumlulukları |
| [docs/YOL-HARITASI.md](docs/YOL-HARITASI.md) | Fazlar, mevcut durum, sıradaki adımlar |
| [docs/DEGISIKLIK-GUNLUGU.md](docs/DEGISIKLIK-GUNLUGU.md) | Önemli mimari değişiklikler (tarih sırasıyla) |
| [docs/BILINEN-HATALAR.md](docs/BILINEN-HATALAR.md) | Tekrarlayan hatalar ve çözümleri |
| [docs/MODEL-ROUTING.md](docs/MODEL-ROUTING.md) | Akıllı router tasarımı ve görev tipleri |

---

## Lisans

Kişisel kullanım için. Bağımlı kütüphanelerin lisansları kendi paketlerinde.
