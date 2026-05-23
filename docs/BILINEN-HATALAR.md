# BSC Forge — Bilinen Hatalar ve Çözümler

> Tekrar aynı tuzağa düşmemek için öğrenilen dersler. Yeni hata çözülünce bu dosyaya ekle.

---

## 1. SQLite: Yeni sohbet çalışmıyor

| Belirti | `Yeni Sohbet` tıklanınca sessiz hata, oturum oluşmuyor |
| Neden | `init_db()` hiç çağrılmıyordu; `chat_history.db` 0 byte |
| Çözüm | `main.py` lifespan + router'da `init_db()` |
| Kod | `backend/main.py`, `backend/routers/chat.py` |

---

## 2. API anahtarı değişti ama hâlâ eski key

| Belirti | `API key expired` / eski key ile istek |
| Neden | Uvicorn süreci bellekte eski `genai.Client` tutuyor |
| Çözüm | Backend yeniden başlat; `reload_env()` + `_reset_clients()` her istekte |
| Kod | `backend/config.py`, `backend/services/llm_manager.py` |

---

## 3. Üstte kalıcı "Bağlantı hatası"

| Belirti | Eski `**HATA:** Bağlantı hatası` mesajı silinmiyor |
| Neden | WS `onerror` + başarısız oturum; hata sohbet listesine yazılıyor |
| Çözüm | Yeni sohbet mesajları temizler; WS nesil kilidi; hata yalnızca bağlantı kurulmadan |
| Kod | `frontend/src/components/ChatWindow.jsx`, `websocket.js` |

---

## 4. Yanıt metni bozuk (tekrarlı heceler)

| Belirti | `klasörckend`, `requirementsrequirements.txt` |
| Neden | ReactMarkdown akış sırasında; token yanlış balona; kümülatif Gemini chunk |
| Çözüm | Akışta düz metin; `streamIndexRef`; delta-only stream |
| Kod | `ChatWindow.jsx`, `llm_manager.py` |

---

## 5. Otomatik model zinciri (Gemini → Groq → Ollama)

| Sıra | Sağlayıcı | Ne zaman |
|------|-----------|----------|
| 1 | Gemini | Varsayılan seçim |
| 2 | Groq | Gemini kota / 429 / 503 |
| 3 | Ollama | Groq da dolu veya `ollama serve` ayakta |

| Kod | `provider_utils.py` (`cascade_from`), `llm_manager.stream_with_notices`, `forge_agent._step_with_cascade` |
| UI | Sarı `fallback` satırı (eskiden yalnızca Groq uyarısı) |
| Yerel | Ollama yoksa `ollama serve` + `ollama pull qwen2.5-coder:1.5b` |

---

## 6. Gemini 429 RESOURCE_EXHAUSTED (ücretsiz kota)

| Belirti | `429`, `free_tier_requests`, günde 20 istek (`gemini-2.5-flash`) |
| Neden | Ajan döngüsü = birden fazla API çağrısı (araç + özet); testler kotayı hızla doldurur |
| Çözüm | Otomatik Groq fallback; liste sorusunda yerel özet (LLM'siz); Groq seç veya billing |
| Kod | `provider_utils.py`, `llm_manager.py`, `forge_agent.py` |
| Not | **Cursor** "Model quota reached" ayrıdır — Forge değil |

---

## 7. Cursor IDE kotası

| Belirti | Altta "Model quota reached", plan yenileme tarihi |
| Neden | Cursor abonelik kotası, proje backend'i değil |
| Çözüm | Bekle / plan yükselt; Forge sohbeti için backend `.env` anahtarları |

---

## 8. Leak olan API anahtarı

| Belirti | Google anahtarı iptal / expired |
| Çözüm | AI Studio'dan eski key'i sil; yeni key → `.env`; asla commit etme |

---

## Geliştirme kontrol listesi (test öncesi)

- [ ] Backend çalışıyor mu? `curl http://localhost:8000/`
- [ ] `.env` içinde geçerli `GEMINI_API_KEY` / `GROQ_API_KEY`
- [ ] **Yeni Sohbet** ile temiz oturum
- [ ] Gemini kotası doluysa model seçici → **Groq**
- [ ] Hata devam ederse `docs/BILINEN-HATALAR.md` güncelle

---

*Son güncelleme: 2026-05-22*
