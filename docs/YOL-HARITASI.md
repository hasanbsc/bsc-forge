# 🔨 BSC Forge — Yol Haritası

> Tüm fazlar, mevcut durum ve sıradaki adımlar tek belgede.
> Son güncelleme: 2026-05-26

---

## Vizyon

AI destekli mikro-ürünler yarattığın, yönettiğin ve kullandığın kişisel bir
portal. İçindeki ajan sistemi sayesinde yeni ürünler de otomatik oluşturulabilir.

## Genel Durum

🟢 **Faz 4 esas olarak tamamlandı** (dosya araçları + akıllı router + write_file approval).
Sıradaki ana hat: **Faz 5 — İlk Ürün (English Buddy)**.

---

## Fazlar

### Faz 1 — Temel Altyapı 🟢

| Bileşen | Durum |
|---------|-------|
| FastAPI backend + WebSocket streaming | ✅ |
| React 19 + Vite frontend (karanlık tema) | ✅ |
| Gemini API entegrasyonu | ✅ |
| Sohbet ekranı + oturum CRUD (oluştur/listele/sil) | ✅ |
| Lifespan `init_db` (yeni sohbet düzeldi) | ✅ |
| README.md kurulum rehberi | ✅ |

---

### Faz 2 — Hibrit Model Sistemi 🟢

| Bileşen | Durum | Not |
|---------|-------|-----|
| Groq API entegrasyonu | ✅ | Llama modelleri |
| DeepSeek API entegrasyonu | ✅ | OpenAI-uyumlu SSE streaming |
| Model kataloğu (`model_registry.py`) | ✅ | Görev etiketleri + öncelik |
| Model seçici arayüzü | ✅ | Lucide ikonları, Otomatik seçenek |
| Ollama (yerel CPU modelleri) | 🟡 | `ollama list` ile katalog; UI sağlık göstergesi kısmi |
| 4 katmanlı otomatik fallback | ✅ | Gemini → Groq → DeepSeek → Ollama |

---

### Faz 3 — Hafıza ve Geçmiş 🟡

| Bileşen | Durum |
|---------|-------|
| SQLite sohbet geçmişi | ✅ |
| Sidebar oturum listesi + silme | ✅ |
| ChromaDB / RAG | ⚪ Bekliyor |

---

### Faz 4 — Forge Ajan (Tool-Calling) 🟢

| Bileşen | Durum |
|---------|-------|
| ReAct ajan döngüsü | ✅ |
| `list_directory` / `read_file` | ✅ |
| `write_file` + UI onay mekanizması | ✅ |
| Çoklu dosya batch approval | ✅ |
| Akıllı model router (`model_router.py`) | ✅ |
| `provider_utils.py` — cascade + hata sınıflandırma | ✅ |
| `routing` + `model_active` WS olayları | ✅ |
| Provider adaptörlerinin ayrı modüllere taşınması | ✅ |
| Sandbox güçlendirme (TOCTOU re-check) | ✅ |
| Kod çalıştırma (sandbox) | ⚪ Bekliyor |
| Web arama aracı | ⚪ Bekliyor |

---

### Faz 5 — İlk Ürün: English Buddy ⚪

| Bileşen | Durum |
|---------|-------|
| Ürün şablon sistemi (`products` tablosu, CRUD) | ✅ Altyapı hazır |
| English Buddy yerleşik ürünü | ✅ Temel (sistem promptu) |
| Seviye seçimi (A1-C2) | ⚪ |
| Hata düzeltme + günlük konu önerileri | ⚪ |
| İlerleyiş takibi | ⚪ |

---

### Faz 6 — Model Eğitimi ⚪

| Bileşen | Durum |
|---------|-------|
| QLoRA fine-tuning (CPU, 0.5B-1.5B) | ⚪ |
| Eğitim verisi hazırlama arayüzü | ⚪ |
| GGUF dönüşümü → Ollama entegrasyonu | ⚪ |

---

## Faz 7 — Kullanıcı Yapılacaklar Listesi (Kullanıcı Talebi 2026-05-25) ⚪

> Hemen yapılmayacak — bir sonraki tur için planlanmış. Kullanıcı "sırada ne var?"
> diye sorduğunda bu listenin üstünden geç.

### 7.1 Üyelik sistemi (opsiyonel giriş) 🟢
- ✅ Anonim sohbet devam ediyor (`browser_id` ile işaretleniyor)
- ✅ E-posta + şifre üyelik (`bcrypt` + JWT, HS256, 7 gün)
- ✅ Üye olunca anonim sohbetler `claim-anonymous` ile hesaba bağlanıyor
- ✅ `sessions` tablosuna `user_id` ve `browser_id` sütunları (idempotent migration)
- ✅ Frontend: `AuthModal` + Sidebar user widget + WS auth-version reconnect
- Kapsam dışı: şifre kurtarma, e-posta doğrulama, refresh token, 2FA

### 7.2 2D Oyun Yaratma Ürünü
- Yeni built-in ürün: "2D Oyun Stüdyosu"
- **Yalnızca yerel model** ile çalışsın (kotaya dokunmadan, gerekirse
  fine-tune edilecek)
- Oyun kodlamada en iyi yerel modeli araştır + seç (örn. Qwen Coder, DeepSeek
  Coder V2, Phi-3 — küçük donanımda hangisi en iyi 2D oyun kodu üretir?)
- Çıktı: Canvas/HTML5 + JavaScript veya Pygame
- Fine-tune edilecekse: `Faz 6 (QLoRA)` üzerinden — kullanıcı eğitim verisini
  birlikte hazırlar

### 7.3 Ürüne Özel Sohbet Teması
- Her ürün kendi sohbet temasına sahip olsun (renkler, ikonlar, arka plan)
- Örnekler:
  - Oyun Stüdyosu → koyu mavi/mor, oyun konsolu hissi, pixel-art ikonlar
  - English Buddy → açık/sıcak tonlar, kitap/balon ikonları
- Ama **ana yapıdan kopmayacak şekilde** — global tema temelini koru, ürün
  yalnızca aksanı değiştirsin
- `Product.theme` alanı (JSON: primary, accent, icon_set) eklenebilir

### 7.4 Arayüzü Profesyonelleştir
- Mevcut UI'da karmaşıklık/aykırılık temizliği
- **Sohbet pinleme** — önemli sohbetleri sidebar'da üstte sabitle
- **Sistem teması algılama** — `prefers-color-scheme` ile açık/koyu otomatik
- **Mobil responsive** — şu an masaüstü ağırlıklı; mobil sidebar drawer
  davranışı, dokunmatik dostu hedefler
- **Glassmorphism** — saydam blur'lu paneller (sidebar, header, kartlar);
  `backdrop-filter: blur(20px)` + yarı saydam renkler
- Ek öneriler: command palette (Cmd+K), mesaj arama, sohbet etiketleri,
  mesaj kopyalama tek tıkla, kod blokları için "Çalıştır" butonu

### 7.5 Bilgisayar Sunucu + Kalıcı Link (Public Tunnel)
- Hedef: bilgisayar açıkken başka cihazlardan aynı linkten erişim
- **Aynı link** zorunluluğu (her seferinde değişmesin)
- Ücretsiz seçenekler değerlendirilecek:
  - **Cloudflare Tunnel** — kalıcı subdomain, ücretsiz (Cloudflare hesabı yeter)
  - **Tailscale Funnel** — `*.ts.net` kalıcı, ücretsiz tier
  - **ngrok** (ücretsiz tier'de link her seferinde değişir; ücretli'de sabit)
  - **localtunnel / serveo** — sabit alt-alan adı opsiyonel ama güvenilirlik düşük
- Tercih edilecek: **Cloudflare Tunnel** (en kararlı + kalıcı + ücretsiz)
- Backend HTTPS arkasından servis edilebilir hale getir; CORS uygun ayarlı

### 7.6 Lokal Model Temizliği
- Gereksiz / kullanılmayan Ollama modelleri kaldırılacak
- Aday: hangileri router/cascade tarafından hiç seçilmiyor? Telemetri loglarına
  bak veya `model_registry.py` priority'lerine göre karar ver
- Minimum tutulması gerekenler (mevcut donanım için):
  - `qwen2.5-coder:7b` — üretim
  - `mistral:7b` — orkestra şefi + Türkçe
  - Diğer 1B-1.5B modeller (llama3.2:1b, qwen2.5-coder:1.5b) gerekiyorsa kalır

### 7.7 `/baslat` ile Anında Hazır
- `/baslat` skill'i çalıştırıldığında **sohbet ekranı doğrudan kullanılabilir**
  olsun (şu an bir-iki tıklama daha gerek)
- Backend + frontend ayağa kalktıktan sonra otomatik browser açılabilir
- Veya: `/baslat` çıktısında sohbet URL'i tıklanabilir link olarak verilir

### 7.8 Model Zaman Aşımı Politikası
- 1-2 dakikadan uzun süren modelleri **otomatik devre dışı bırak**
- Şu an `provider_utils.py` 503/timeout durumlarını yakalıyor ama "bu model
  çok yavaş" tespiti yok
- Önerilen: cascade'de bir model 90+ saniye sürerse o adıma cancel, sonraki
  sağlayıcıya geç. Telemetri: hangi modeller sürekli yavaş?
- 7B+ yerel modeller dahil (Codestral 22B, DeepSeek V2 16B vb. dikkatli olunsun)

### 7.9 Mimari Temizlik (devamlı, küçük dozlarda)
- Kullanılmayan kod / sinyal / dosya kaldırılacak
- Aday taramaları: dead imports, unreferenced functions, eski model entry'leri,
  CSS'te kullanılmayan sınıflar

---

## Sıradaki Adımlar (Öncelik Sırasıyla)

1. **Faz 4 kapanış** — Kod çalıştırma (sandbox) ve web arama aracı.
2. **Faz 5 ilerleyiş** — English Buddy seviye seçimi + hata düzeltme.
3. **Faz 3 ChromaDB** — Uzun hafıza / RAG.
4. **Faz 2 Ollama UX** — Sunucu sağlık göstergesi UI'da.
5. **Faz 7 — Kullanıcı Yapılacaklar** (yukarı listeyi sırasıyla yap).

---

## Teknik Yığın

| Katman | Teknoloji |
|--------|-----------|
| Backend | Python 3.11+, FastAPI, WebSocket, SQLite (aiosqlite) |
| Frontend | React 19, Vite, Vanilla CSS |
| LLM | Gemini API, Groq API, DeepSeek API, Ollama |
| Çalışma Ortamı | Windows + WSL 2 Ubuntu |

---

## Kararlar (Mimari Kayıt)

| Tarih | Karar | Gerekçe |
|-------|-------|---------|
| 2026-05-22 | Python + FastAPI backend | AI ekosistemi Python merkezli |
| 2026-05-22 | React + Vite frontend | Hızlı geliştirme, modern UI |
| 2026-05-22 | Hibrit model yaklaşımı | GPU yok; bulut API + CPU yerel |
| 2026-05-22 | Türkçe arayüz | Kullanıcı tercihi |
| 2026-05-22 | Faz 2 → Faz 4 öncelik | RAG'den önce tool-calling daha hızlı değer |
| 2026-05-23 | DeepSeek fallback zincire eklendi | Groq kotası dolduğunda 3. yedek |
| 2026-05-23 | Akıllı router (NLP sınıflandırma) | Kullanıcı provider seçmek zorunda kalmasın |
| 2026-05-24 | Ürün şablon sistemi | Mikro-ürün fabrikası vizyonu |
| 2026-05-25 | `forge_agent.py` provider modüllere bölündü | 900 → 475 satır; sorumluluklar ayrıştı |

---

## İlgili Belgeler

- [docs/MIMARI.md](MIMARI.md) — Kod mimarisi ve istek akışı
- [docs/DEGISIKLIK-GUNLUGU.md](DEGISIKLIK-GUNLUGU.md) — Tarihli değişiklik özeti
- [docs/BILINEN-HATALAR.md](BILINEN-HATALAR.md) — Tekrar etmemek için dersler
- [docs/MODEL-ROUTING.md](MODEL-ROUTING.md) — Yönlendirme tasarımı
