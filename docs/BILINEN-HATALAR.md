# 🐛 BSC Forge — Bilinen Hatalar ve Dersler

> Aynı tuzağa düşmemek için. Yeni hata çözülünce buraya ekle.
> Son güncelleme: 2026-05-25

---

## 1. Yeni sohbet sessizce başarısız oluyordu

| Alan | Detay |
|------|------|
| Belirti | "Yeni Sohbet" tıklanınca oturum oluşmuyor |
| Neden | `init_db()` hiç çağrılmıyordu; `chat_history.db` 0 byte |
| Çözüm | `main.py` lifespan'de `chat_history.init_db()` + `product_store.init_table()` |
| Kod | `backend/main.py` |

---

## 2. API anahtarı değişti ama hâlâ eski key kullanılıyor

| Alan | Detay |
|------|------|
| Belirti | `API key expired` / eski key ile istek |
| Neden | Config startup'ta yüklenir, değişmez |
| Çözüm | `.env` güncellendiğinde **backend yeniden başlatılmalı** (`python3 main.py`) |
| Kod | `backend/config.py` |

> Not: Eski sürümlerde her istekte `reload_env()` + `_reset_clients()` çağrılıyordu;
> thread-unsafe ve gereksiz gecikme nedeniyle 2026-05-23'te kaldırıldı.

---

## 3. Üstte kalıcı "Bağlantı hatası" mesajı

| Alan | Detay |
|------|------|
| Belirti | Eski `**HATA:** Bağlantı hatası` mesajı silinmiyor |
| Neden | WS `onerror` + başarısız oturum; hata sohbet listesine yazılıyor |
| Çözüm | Yeni sohbet mesajları temizler; WS nesil kilidi; hata yalnızca bağlantı kurulamadığında |
| Kod | `frontend/src/components/ChatWindow.jsx`, `services/websocket.js` |

---

## 4. Yanıt metni bozuk (tekrarlı heceler)

| Alan | Detay |
|------|------|
| Belirti | `klasörckend`, `requirementsrequirements.txt` |
| Neden | ReactMarkdown akış sırasında; token yanlış balona; kümülatif Gemini chunk'ı |
| Çözüm | Akışta düz metin; `streamIndexRef`; delta-only stream |
| Kod | `ChatWindow.jsx`, `services/llm_manager.py` |

---

## 5. Gemini 429 RESOURCE_EXHAUSTED (ücretsiz kota)

| Alan | Detay |
|------|------|
| Belirti | `429`, `free_tier_requests`, günde 20 istek (`gemini-2.5-flash`) |
| Neden | Ajan döngüsü = birden fazla API çağrısı (araç + özet); testler kotayı hızla doldurur |
| Çözüm | Otomatik Groq fallback; liste sorularında yerel özet (LLM'siz, `_local_tool_summary`); Groq'a manuel geçiş; billing |
| Kod | `services/provider_utils.py`, `services/forge_agent.py` |

---

## 6. Tool çağrısı metne yazılıyor (Groq Llama 3.3)

| Alan | Detay |
|------|------|
| Belirti | Yanıtta `<function(write_file)>{...}</function>` görünür |
| Neden | Groq Llama bazen function call yerine düz metin döndürür |
| Çözüm | `forge_agent._recover_tool_calls_from_text` ile parse edip gerçek tool çağrısına çevriliyor |
| Kod | `backend/services/forge_agent.py` |

---

## 7. Otomatik fallback zinciri

| Sıra | Sağlayıcı | Ne zaman devreye girer |
|------|-----------|----------------------|
| 1 | Gemini | Varsayılan / akıllı router seçimi |
| 2 | Groq | Gemini kota / 429 / 5xx / MALFORMED_FUNCTION_CALL |
| 3 | DeepSeek | Groq kota / capacity / 5xx |
| 4 | Ollama | Tüm bulut sağlayıcılar başarısız ve `ollama serve` ayakta |

| Kod | `services/provider_utils.py:cascade_from`, `services/forge_agent.py:_step_with_cascade` |
| UI | Sarı `fallback` satırı |
| Yerel kurulum | `ollama serve` + `ollama pull qwen2.5-coder:1.5b` |

---

## 8. Cursor IDE kotası (bizim ürün değil)

| Alan | Detay |
|------|------|
| Belirti | Cursor'da "Model quota reached", plan yenileme tarihi |
| Neden | Cursor abonelik kotası, BSC Forge backend'iyle alakasız |
| Çözüm | Bekle / plan yükselt. Forge sohbeti için `.env` API anahtarları geçerli kaldığı sürece sorun yok. |

---

## 9. Leak olan API anahtarı

| Alan | Detay |
|------|------|
| Belirti | Google anahtarı iptal / expired |
| Çözüm | AI Studio'dan eski key'i sil; yeni key → `.env`; **asla commit etme** |

---

## Test Öncesi Kontrol Listesi

- [ ] Backend çalışıyor mu? `curl http://localhost:8000/health`
- [ ] `.env` içinde geçerli `GEMINI_API_KEY` / `GROQ_API_KEY`
- [ ] **Yeni Sohbet** ile temiz oturum
- [ ] Gemini kotası doluysa model seçici → **Groq**
- [ ] Yeni hata çözüldü ama buraya eklemedin mi? **Hemen ekle.**
