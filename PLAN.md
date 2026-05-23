# 🔨 BSC Forge — Uygulama Planı

> Kişisel Yapay Zeka Ürün Fabrikası

## Vizyon
AI destekli mikro-ürünler yarattığın, yönettiğin ve kullandığın kişisel bir portal.
İçindeki ajan sistemi sayesinde yeni ürünler de otomatik oluşturulabilir.

---

## Fazlar

### Faz 1: Temel Altyapı ← **KAPANIYOR**
- FastAPI backend + WebSocket streaming ✅
- React/Vite frontend (karanlık tema, premium UI) ✅
- Gemini API entegrasyonu ✅
- Temel sohbet ekranı + oturum CRUD (oluştur / listele / sil) ✅
- Kalan: README kurulum rehberi

### Faz 2: Hibrit Model Sistemi
- Groq API entegrasyonu ✅
- DeepSeek API entegrasyonu ✅ (config + fallback; streaming testi bekliyor)
- Model kataloğu (`model_registry.py`) ✅ — görev etiketleri + öncelik sistemi
- Model seçici arayüzü ✅ — Lucide ikonlar, Otomatik seçenek
- Ollama (yerel CPU modelleri) — kısmen (`ollama list` ile katalog; UI sağlık göstergesi eksik)
- Otomatik fallback ✅ — Gemini → Groq → DeepSeek → Ollama (4 katman)

### Faz 3: Hafıza ve Geçmiş
- SQLite sohbet geçmişi ✅
- Sohbet listesi sidebar ✅
- ChromaDB (RAG / vektör hafıza) — bekliyor

### Faz 4: Forge Ajan (Tool-Calling) ← **~%90 TAMAMLANDI**
- ReAct ajan döngüsü ✅ (v1)
- Dosya listeleme / okuma ✅
- Akıllı model router (`model_router.py`) ✅ — görev sınıflandırma → otomatik model seçimi
- `provider_utils.py` ✅ — merkezi fallback + hata sınıflandırma
- `routing` + `model_active` WS olayları ✅
- Dosya yazma (`write_file`) — bekliyor (onay mekanizmalı)
- Kod çalıştırma — bekliyor (sandbox)
- Web arama — bekliyor

### Faz 5: İlk Ürün — İngilizce Pratik Arkadaşı
- Ürün şablon sistemi
- English Buddy: seviye seçimi, hata düzeltme
- Günlük konu önerileri

### Faz 6: Model Eğitimi
- QLoRA fine-tuning (CPU, 0.5B-1.5B modeller)
- Eğitim verisi hazırlama arayüzü
- GGUF dönüşümü → Ollama entegrasyonu

---

## Operasyonel notlar

Tekrarlayan hatalar ve çözümler: [docs/BILINEN-HATALAR.md](docs/BILINEN-HATALAR.md)  
Akıllı model yönlendirme: [docs/MODEL-ROUTING.md](docs/MODEL-ROUTING.md)

---

## Teknik Yığın
- **Backend:** Python 3.11+, FastAPI, SQLite, ChromaDB
- **Frontend:** React 18+, Vite, Vanilla CSS
- **AI:** Google Gemini API, Groq API, Ollama
- **Çalışma Ortamı:** Windows (WSL 2 Ubuntu mevcut)
