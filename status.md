# 🔨 BSC Forge — Proje Durumu

> Son Güncelleme: 2026-05-23

## Genel Durum: 🟡 Faz 4 tamamlandı (dosya araçları + akıllı router) — Faz 2 / Faz 5 sırada

---

## Faz Özeti

| Faz | PLAN.md | Gerçek durum |
|-----|---------|--------------|
| **Faz 1** — Temel altyapı | Şu an buradayız | 🟢 ~%95 — sohbet, WS, UI, DB init çalışıyor |
| **Faz 2** — Hibrit modeller | Sırada | 🟡 Kısmen — Gemini + Groq + seçici var; Ollama durumu “yapılandırılmadı”, otomatik fallback yok |
| **Faz 3** — Hafıza ve geçmiş | Sırada | 🟡 Kısmen — SQLite geçmiş + sidebar listesi var; ChromaDB/RAG yok |
| **Faz 4** — Forge Ajan | **Şu an** | 🟢 ~%90 — dosya araçları + akıllı model router + 4-katmanlı fallback |
| **Faz 5** — İlk ürün | Bekliyor | ⚪ — English Buddy vb. yok |
| **Faz 6** — Model eğitimi | Bekliyor | ⚪ |

---

## Faz 1: Temel Altyapı
**Durum:** 🟢 Neredeyse tamam

| Bileşen | Durum | Notlar |
|---------|-------|--------|
| Proje yapısı | 🟢 Tamamlandı | Backend / frontend / `.env` |
| Backend (FastAPI) | 🟢 Tamamlandı | LLM Manager, Chat API, lifespan `init_db` |
| Frontend (React/Vite) | 🟢 Tamamlandı | Karanlık tema, sidebar, model seçici |
| WebSocket streaming | 🟢 Tamamlandı | Token akışı çalışıyor |
| SQLite sohbet geçmişi | 🟢 Tamamlandı | Oturum oluşturma, listeleme, mesaj kaydı |
| Oturum silme | 🟢 Tamamlandı | Sidebar çöp kutusu + `DELETE /sessions/{id}` |
| İlk uçtan uca test | 🟢 Tamamlandı | Gemini yanıt, yeni sohbet, API key reload |
| README / kurulum dokümanı | ⚪ Bekliyor | Tek komutla başlatma rehberi yok |

---

## Faz 2: Hibrit Model Sistemi (kısmi)
**Durum:** 🔵 Devam ediyor

| Bileşen | Durum | Notlar |
|---------|-------|--------|
| Gemini API | 🟢 Tamamlandı | `gemini-2.5-flash` |
| Groq API | 🟢 Tamamlandı | Llama modelleri listeleniyor |
| DeepSeek API | 🟡 Kısmen | Config + fallback zincirinde yerini aldı; streaming testi bekliyor |
| Model seçici UI | 🟢 Tamamlandı | Lucide ikonlar: Sparkles(Oto) / Cloud / Cpu(Yerel) |
| Ollama (yerel) | 🟡 Kısmen | `ollama list` ile katalog; sağlık kontrolü `/api/models`’de mevcut |
| Otomatik fallback | 🟢 Tamamlandı | Gemini → Groq → DeepSeek → Ollama (4 katman) |
| Akıllı model kataloğu | 🟢 Tamamlandı | `model_registry.py`: görev etiketleri + öncelik sistemi |

---

## Faz 3: Hafıza ve Geçmiş (kısmi)
**Durum:** 🔵 Devam ediyor

| Bileşen | Durum | Notlar |
|---------|-------|--------|
| SQLite geçmiş | 🟢 Tamamlandı | `data/chat_history.db` |
| Sohbet listesi sidebar | 🟢 Tamamlandı | Son sohbetler, seçim, silme |
| ChromaDB / RAG | ⚪ Bekliyor | PLAN’da Faz 3 |

---

## Faz 4: Forge Ajan
**Durum:** 🟢 ~%90 tamamlandı

| Bileşen | Durum | Notlar |
|---------|-------|--------|
| `list_directory` | 🟢 Tamamlandı | Sandbox: proje kökü altı |
| `read_file` | 🟢 Tamamlandı | 80KB üst sınır, UTF-8 metin |
| Tool-calling (Gemini) | 🟢 Tamamlandı | WebSocket `tool` + `token` olayları |
| Tool-calling (Groq fallback) | 🟢 Tamamlandı | Gemini hata → Groq |
| Akıllı model router | 🟢 Tamamlandı | `model_router.py`: görev sınıflandırma → en uygun model seçimi |
| Routing bildirim (UI) | 🟢 Tamamlandı | `routing` WS olayı: “🎯 Dosya sorusu → Gemini 2.5 Flash” |
| `model_active` WS olayı | 🟢 Tamamlandı | Her yanıt öncesi hangi modelin çalıştığı bildirilir |
| `provider_utils.py` | 🟢 Tamamlandı | Hata sınıflandırma + fallback zinciri merkezi modül |
| UI araç göstergesi | 🟢 Tamamlandı | Sidebar’da mavi “Araç” satırı |
| Dosya yazma (`write_file`) | ⚪ Bekliyor | Onay mekanizmalı güvenli yazma |
| Kod çalıştırma | ⚪ Bekliyor | Sandbox’lı terminal aracı |
| Web arama | ⚪ Bekliyor | |

---

## Önerilen sıradaki adımlar

1. **Faz 4 devam** — `write_file` (onaylı), terminal/kod çalıştırma (sandbox).
2. **Faz 2 bitir** — DeepSeek streaming testi; Ollama `ollama serve` durumu UI'da göster.
3. **Faz 5 başlat** — İlk ürün: İngilizce Pratik Arkadaşı şablonu.
4. **Faz 1 kapat** — `README.md` kurulum rehberi.
5. **Faz 3 ChromaDB** — RAG / uzun hafıza.

---

## Geliştirme Günlüğü

### 2026-05-23
- ✅ **DeepSeek API desteği:** config + `reload_env` + fallback zinciri (Gemini → Groq → DeepSeek → Ollama)
- ✅ **`model_registry.py`:** görev etiketleri (file_ops, coding, turkish, reasoning, weather, fast), öncelik sistemi, Ollama katalog entegrasyonu
- ✅ **`model_router.py`:** NLP sınıflandırma ile otomatik model seçimi; `RouteDecision` + `routing` WS olayı
- ✅ **`provider_utils.py`:** fallback zinciri, hata sınıflandırma, `model_active_event` merkezi modül
- ✅ **`routers/models.py`:** `/api/models` → dinamik katalog + Ollama sağlık kontrolü
- ✅ **`main.py` yeniden yapılandırıldı:** models router ayrıldı, DeepSeek sağlık ucu eklendi
- ✅ **Chat router güncellendi:** `model_router.route()` entegrasyonu, `routing` + `model_active` olayları
- ✅ **UI — ModelSelector:** Lucide ikonlar (Sparkles/Cloud/Cpu), `Otomatik (Akıllı)` seçeneği üstte
- ✅ **UI — App.jsx:** varsayılan sağlayıcı `auto`, oturum silme onay diyaloğu, session-error banner

### 2026-05-22 (gece)
- ✅ **Akıllı model router:** görev tipi (kod, TR, EN, dosya, hava, …) → en uygun bulut/yerel model
- ✅ Çoklu Ollama: `ollama list` ile yüklü modeller otomatik kataloga eklenir
- ✅ UI: **Otomatik (Akıllı)** seçeneği + `docs/MODEL-ROUTING.md` araştırma özeti

### 2026-05-22 (akşam — devam)
- ✅ **3 katmanlı fallback:** Gemini → Groq → Ollama (+ liste için yerel araç)
- ✅ `docs/BILINEN-HATALAR.md` — tekrarlayan hatalar ve çözümler
- ✅ Gemini 429 → otomatik Groq fallback + liste sorusunda yerel özet (kota tasarrufu)

### 2026-05-22 (akşam)
- ✅ **Forge Ajan v1**: `tools.py`, `forge_agent.py`, WebSocket tool olayları
- ✅ Test: “backend klasöründeki dosyalar” sorusu araçlarla yanıtlanıyor

### 2026-05-22 (öğleden sonra)
- ✅ `init_db` uygulama başlangıcına eklendi (yeni sohbet / liste düzeldi)
- ✅ `.env` API anahtarı değişince LLM client yenileniyor
- ✅ Yeni sohbet tıklanınca eski hata mesajları temizleniyor
- ✅ Sohbet silme: sidebar + REST `DELETE`
- ✅ Gemini ile uçtan uca WebSocket testi başarılı

### 2026-05-22 (sabah)
- ✅ Proje planı oluşturuldu ve onaylandı
- ✅ Donanım analizi yapıldı (i7-7700HQ, 16GB RAM, GPU yok)
- ✅ Hibrit model stratejisi belirlendi (Gemini/Groq + Ollama CPU)
- ✅ Proje ismi seçildi: **BSC Forge**
- 🔨 Faz 1 geliştirmesi başladı

---

## Bilinen hatalar (tekrar etme)

Tüm dersler: **[docs/BILINEN-HATALAR.md](docs/BILINEN-HATALAR.md)**

---

## Kararlar

| Tarih | Karar | Gerekçe |
|-------|-------|---------|
| 2026-05-22 | Python + FastAPI backend | AI ekosistemi Python merkezli |
| 2026-05-22 | React + Vite frontend | Hızlı geliştirme, modern UI |
| 2026-05-22 | Hibrit model yaklaşımı | GPU yok, bulut API + CPU yerel |
| 2026-05-22 | Türkçe arayüz | Kullanıcı tercihi |
| 2026-05-22 | Sıradaki odak: Faz 2 bitir → Faz 4 ajan | RAG’den önce tool-calling daha hızlı kullanıcı değeri |
| 2026-05-23 | DeepSeek fallback zincire eklendi | Groq kota dolduğunda 3. yedek sağlayıcı olarak |
| 2026-05-23 | Akıllı router (NLP sınıflandırma) | Kullanıcı provider seçmek zorunda kalmasın, sistem en uygununu seçsin |
