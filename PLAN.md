# 🔨 BSC Forge — Uygulama Planı

> Kişisel Yapay Zeka Ürün Fabrikası

## Vizyon
AI destekli mikro-ürünler yarattığın, yönettiğin ve kullandığın kişisel bir portal.
İçindeki ajan sistemi sayesinde yeni ürünler de otomatik oluşturulabilir.

---

## Fazlar

### Faz 1: Temel Altyapı ← **ŞU AN BURADAYIZ**
- FastAPI backend + WebSocket streaming
- React/Vite frontend (karanlık tema, premium UI)
- Gemini API entegrasyonu (ilk bulut model)
- Temel sohbet ekranı

### Faz 2: Hibrit Model Sistemi
- Groq API entegrasyonu
- Ollama (yerel CPU modelleri)
- Model seçici arayüzü
- Otomatik fallback

### Faz 3: Hafıza ve Geçmiş
- SQLite sohbet geçmişi
- ChromaDB (RAG / vektör hafıza)
- Sohbet listesi sidebar

### Faz 4: Forge Ajan (Tool-Calling)
- ReAct ajan döngüsü
- Dosya okuma/yazma/listeleme araçları
- Kod çalıştırma
- Web arama

### Faz 5: İlk Ürün — İngilizce Pratik Arkadaşı
- Ürün şablon sistemi
- English Buddy: seviye seçimi, hata düzeltme
- Günlük konu önerileri

### Faz 6: Model Eğitimi
- QLoRA fine-tuning (CPU, 0.5B-1.5B modeller)
- Eğitim verisi hazırlama arayüzü
- GGUF dönüşümü → Ollama entegrasyonu

---

## Teknik Yığın
- **Backend:** Python 3.11+, FastAPI, SQLite, ChromaDB
- **Frontend:** React 18+, Vite, Vanilla CSS
- **AI:** Google Gemini API, Groq API, Ollama
- **Çalışma Ortamı:** Windows (WSL 2 Ubuntu mevcut)
