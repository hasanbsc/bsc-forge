# Akıllı Model Yönlendirme (Model Routing)

## Soru: “Hangi model daha iyi?” seçen bir model var mı?

**Evet — ama genelde ayrı bir “router” katmanı olarak çalışır**, sohbet modelinin kendisi değil.

| Yaklaşım | Örnek | Nasıl çalışır |
|----------|--------|----------------|
| **Bulut meta-router** | [OpenRouter `openrouter/auto`](https://openrouter.ai/docs/guides/routing/routers/auto-router) (NotDiamond) | Prompt analiz → en uygun model → yanıtta hangi model kullanıldığı yazar |
| **Araştırma / açık kaynak** | [RouteLLM](https://arxiv.org/abs/2404.06035), [LLMRouter](https://github.com/ulab-uiuc/LLMRouter), FineRouter (2025) | Küçük sınıflandırıcı veya öğrenilmiş router |
| **Kural + skor (bizim v1)** | BSC Forge `model_router.py` | Anahtar kelime + dil + karmaşıklık → görev tipi → kayıttaki en iyi model |
| **Mini LLM router (v2 plan)** | Gemini Flash / Groq 8B | “Bu prompt için kategori: coding” JSON döndürür (1 ucuz istek) |

**Önemli:** Hava durumu, borsa, güncel haber gibi **canlı veri** için hiçbir dil modeli tek başına yeterli değil — **API aracı** (weather tool) gerekir. Router bu tip soruları `weather` olarak işaretler; ileride web/weather tool bağlanır.

---

## BSC Forge görev tipleri

| Görev | Örnek | Tercih edilen model tipi |
|-------|--------|---------------------------|
| `file_ops` | “backend klasörünü listele” | Ajan + araçlar (kota dostu yerel özet) |
| `coding` | “Python API yaz”, “refactor” | Yerel Qwen Coder / Groq 70B |
| `turkish` | Türkçe sohbet | Gemini Flash / çok dilli |
| `english` | English chat | Groq 70B / Gemini |
| `reasoning` | Mimari, karşılaştırma, uzun analiz | Groq 70B / Gemini |
| `weather` | “İstanbul hava durumu” | Genel model + *gelecekte weather API* |
| `fast` | Kısa soru, selam | Groq 8B / küçük yerel |

Fallback zinciri değişmedi: **Gemini → Groq → Ollama**.

---

## Kullanım

- UI: Model seçici → **Otomatik (Akıllı)**
- API: `POST /api/route` body `{ "message": "..." }`
- WebSocket: `"routing": "auto"` veya `provider: "auto"`

Yanıtta `routing` olayı: hangi görev ve hangi model seçildiği.

---

*Son güncelleme: 2026-05-22*
