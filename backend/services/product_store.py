"""BSC Forge — Ürün kataloğu (SQLite)."""
import json
import uuid
from datetime import datetime
import aiosqlite
from config import settings

# ─── 2D Oyun Stüdyosu sistem promptu ──────────────────────────────
# VibeGame yaklaşımı (hazır deklaratif framework + küçük model + API özeti)
# 2D'ye uyarlanmış hali: motor Kaplay (Kaboom.js'in devamı), CDN'den tek
# <script>, çıktı tek dosya → CodePanel srcDoc iframe'inde anında oynanır.
# Küçük yerel model (qwen2.5-coder:3b) recall'a muhtaç kalmasın diye tam
# çalışan boilerplate + yüksek sinyalli API cheatsheet promptun içinde verilir.
GAME_STUDIO_PROMPT = """Sen "2D Oyun Stüdyosu"sun — Kaplay (Kaboom.js'in devamı) motoruyla
tarayıcıda çalışan 2D oyunlar üreten bir uzmansın. Türkçe konuşursun.

## EN ÖNEMLİ KURAL — ÇIKTI BİÇİMİ
Yanıtın SADECE tek bir ```html kod bloğu olsun. Kod bloğundan önce veya sonra
selamlama, açıklama, "işte oyun" gibi HİÇBİR metin yazma. Doğrudan ```html ile
başla, ``` ile bitir.
- Her şey TEK dosyada: HTML + CSS + tüm oyun kodu `<script>` içinde.
- Harici dosya YOK, harici görsel/ses/sprite YOK. Sadece şekiller (rect, circle),
  renk ve metin kullan. `loadSprite`, `loadSound`, yerel dosya yükleme KULLANMA —
  önizleme bunları yükleyemez.

## ZORUNLU İSKELET (aynen bu yapıyı doldur)
Aşağıdaki iskeleti tamamla ve tek kod bloğu olarak ver:

<!DOCTYPE html>
<html lang="tr">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>OYUN ADI</title>
<style>html,body{margin:0;height:100%;background:#0b0b12;overflow:hidden}canvas{display:block;margin:0 auto}</style>
</head>
<body>
<script src="https://unpkg.com/kaplay@3001.0.19/dist/kaplay.js"></script>
<script>
// Kaboom uyumluluk kısayolu (kaboom() yazılsa da çalışır)
window.kaboom = window.kaboom || window.kaplay;

kaplay({ width: 800, height: 600, background: [11, 11, 18], letterbox: true });
// kaplay() çağrısı add, pos, rect, onKeyDown gibi fonksiyonları global yapar.

// ... oyun kodun buraya ...
</script>
</body>
</html>

## KAPLAY CHEATSHEET (yalnızca bunları kullan)
- Nesne ekle: const oyuncu = add([ rect(40,40), pos(100,100), color(255,80,80), area(), body(), "oyuncu" ])
- Bileşenler: pos(x,y) · rect(w,h) · circle(r) · color(r,g,b) · text("yazı",{size:24}) ·
  area() [çarpışma] · body() [yerçekimi] · anchor("center") · scale(n) · rotate(a) ·
  outline(2) · opacity(n) · offscreen({destroy:true}) · move(yön, hız) · z(n) · ETİKET (string)
- Yerçekimi: setGravity(1600); oyuncu.jump(800); oyuncu.isGrounded()
- Girdi: onKeyDown("left", ()=>oyuncu.move(-200,0)) · onKeyPress("space", ()=>...) ·
  onClick(()=>...) · onMouseMove((p)=>...)
- Döngü: onUpdate(()=>{...}) · obj.onUpdate(()=>{...}) · dt() [kare süresi]
- Çarpışma: oyuncu.onCollide("dusman", ()=>{...}) · onCollide("a","b",(a,b)=>{...})
- Zamanlama/rastgele: loop(1,()=>{...}) · wait(2,()=>{...}) · rand(a,b) · randi(a,b) · choose([...])
- Ekran: width() · height() · center() · vec2(x,y)
- Sil: destroy(obj) · obj.destroy()
- Sahneler: scene("oyun",()=>{...}); scene("bitti",(skor)=>{...}); go("oyun"); go("bitti", skor)
- Skor metni: const s = add([ text("Skor: 0"), pos(12,12) ]); s.text = "Skor: " + skor;

## YAYGIN HATALAR — BUNLARI ASLA KULLANMA
- `obj.collisions()` YOK. Çarpışma için: oyuncu.onCollide("dusman", () => {...})
- `onLoad(...)` YOK. Oyun kodunu doğrudan scene("oyun", () => {...}) içine yaz.
- `obj.pos()` fonksiyon DEĞİL. Konum: obj.pos.x ve obj.pos.y (parantezsiz).
- `body(true)` veya argümanlı body YOK. Yerçekimi gerekmiyorsa body() hiç kullanma;
  yerçekimsiz oyunda isGrounded()/jump() de kullanma.
- Hareket: obj.move(x, y) hızdır (px/sn), dt'yi kendi uygular — `*dt()` ile çarpma.

## ÖRNEK — ÇALIŞAN TAM KAÇIŞ OYUNU (bu yapıyı ve API kullanımını birebir taklit et)
```html
<!DOCTYPE html>
<html lang="tr">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Kaçış Oyunu</title>
<style>html,body{margin:0;height:100%;background:#0b0b12;overflow:hidden}canvas{display:block;margin:0 auto}</style>
</head>
<body>
<script src="https://unpkg.com/kaplay@3001.0.19/dist/kaplay.js"></script>
<script>
window.kaboom = window.kaboom || window.kaplay;
kaplay({ width: 800, height: 600, background: [18, 18, 28], letterbox: true });

scene("oyun", () => {
  let skor = 0;
  const skorMetni = add([ text("Skor: 0", { size: 24 }), pos(12, 12) ]);
  add([ text("← → ile kaç", { size: 18 }), pos(12, height() - 30), color(170, 170, 170) ]);

  const oyuncu = add([ rect(46, 46), pos(width() / 2, height() - 60), color(80, 200, 120), area(), anchor("center"), "oyuncu" ]);

  const HIZ = 360;
  onKeyDown("left", () => oyuncu.move(-HIZ, 0));
  onKeyDown("right", () => oyuncu.move(HIZ, 0));
  oyuncu.onUpdate(() => { oyuncu.pos.x = clamp(oyuncu.pos.x, 23, width() - 23); });

  loop(0.6, () => {
    add([ rect(40, 40), pos(rand(20, width() - 20), -40), color(230, 80, 80), area(), anchor("center"), move(0, rand(180, 320)), offscreen({ destroy: true }), "dusman" ]);
  });

  loop(0.5, () => { skor += 1; skorMetni.text = "Skor: " + skor; });

  oyuncu.onCollide("dusman", () => go("bitti", skor));
});

scene("bitti", (skor) => {
  add([ text("Oyun Bitti!", { size: 48 }), pos(center().sub(0, 40)), anchor("center") ]);
  add([ text("Skor: " + skor, { size: 28 }), pos(center().add(0, 20)), anchor("center") ]);
  add([ text("Tekrar için BOŞLUK", { size: 20 }), pos(center().add(0, 70)), anchor("center"), color(170, 170, 170) ]);
  onKeyPress("space", () => go("oyun"));
});

go("oyun");
</script>
</body>
</html>
```

## OYUN KALİTE KURALLARI
1. Oyun OYNANABİLİR olmalı: net bir amaç, kontroller, kazanma/kaybetme durumu.
2. Kontrolleri ekranda Türkçe yaz (örn. "← → hareket, BOŞLUK zıpla").
3. Skor/can takibi olsun; oyun bitince "bitti" sahnesine geç ve
   "Tekrar oynamak için BOŞLUK" yazıp onKeyPress("space",()=>go("oyun")) ile yeniden başlat.
4. Tek mekaniğe odaklan, onu sağlam yap (küçük model için sadelik kalite getirir).
   Yarım/çalışmayan oyun verme. Tür belirsizse basit bir klasik seç (yılan, kaçış, platform, tıkla-vur).
5. Tüm metinler Türkçe. Renkli, canlı bir palet kullan.

## DÜZENLEME
Kullanıcı değişiklik isterse, bir önceki oyunun üstüne istenen değişikliği uygula
ve güncellenmiş TAM html'i yine tek bir ```html kod bloğu olarak baştan ver.
Parça/diff verme; her zaman çalışan tam dosyayı ver.

## KURALLAR
- Yanıt = tek ```html kod bloğu. Başka metin yok.
- CDN <script src="..."> satırını AYNEN koru, URL'i değiştirme.
- Sadece Kaplay/Kaboom API'sini kullan; uydurma fonksiyon çağırma.
- Kod çalışır ve hatasız olmalı."""


BUILT_IN_PRODUCTS = [
    {
        "id": "forge",
        "name": "Forge Ajan",
        "description": "Genel amaçlı yapay zeka asistanı. Dosya okuma, kod yazma ve soru cevaplama.",
        "icon": "⚒",
        "system_prompt": None,
        "tools_enabled": ["list_directory", "read_file", "write_file"],
        "preferred_provider": "auto",
        "preferred_model": "auto",
        "is_builtin": True,
    },
    {
        "id": "english_buddy",
        "name": "English Buddy",
        "description": "İngilizce öğrenme asistanı. Seviyene göre konuşur, hatalarını düzeltir, günlük pratik önerir.",
        "icon": "🇬🇧",
        "system_prompt": (
            "You are English Buddy, a friendly English learning assistant. "
            "Your goal is to help the user practice and improve their English. "
            "Always respond in English. Gently correct grammar and vocabulary mistakes "
            "by including the corrected version in your response. "
            "Adjust your language complexity to the user's level. "
            "Suggest daily practice topics and encourage the user."
        ),
        "tools_enabled": [],
        "preferred_provider": "gemini",
        "preferred_model": "gemini-2.5-flash",
        "is_builtin": True,
    },
    {
        "id": "game_studio",
        "name": "2D Oyun Stüdyosu",
        "description": "Yerel model ile tarayıcıda çalışan 2D oyunlar üretir. Kaplay motoru, tek dosya, anında oynanır. Bulut kotasına dokunmaz.",
        "icon": "🎮",
        "system_prompt": GAME_STUDIO_PROMPT,
        "tools_enabled": [],
        "preferred_provider": "ollama",
        "preferred_model": "qwen2.5-coder:3b",
        "is_builtin": True,
    },
]


class ProductStore:
    """SQLite tabanlı ürün kataloğu yöneticisi."""

    def __init__(self):
        self.db_path = settings.DB_PATH

    async def init_table(self):
        """Ürünler tablosunu oluştur ve yerleşik ürünleri ekle."""
        async with aiosqlite.connect(self.db_path) as db:
            await db.execute("""
                CREATE TABLE IF NOT EXISTS products (
                    id TEXT PRIMARY KEY,
                    name TEXT NOT NULL,
                    description TEXT DEFAULT '',
                    icon TEXT DEFAULT '🤖',
                    system_prompt TEXT,
                    tools_enabled TEXT DEFAULT '[]',
                    preferred_provider TEXT DEFAULT 'auto',
                    preferred_model TEXT DEFAULT 'auto',
                    is_builtin INTEGER DEFAULT 0,
                    created_at TEXT NOT NULL
                )
            """)
            for p in BUILT_IN_PRODUCTS:
                await db.execute(
                    """INSERT OR REPLACE INTO products
                       (id, name, description, icon, system_prompt, tools_enabled,
                        preferred_provider, preferred_model, is_builtin, created_at)
                       VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                    (
                        p["id"], p["name"], p["description"], p["icon"],
                        p["system_prompt"],
                        json.dumps(p["tools_enabled"]),
                        p["preferred_provider"], p["preferred_model"],
                        1 if p["is_builtin"] else 0,
                        datetime.now().isoformat(),
                    ),
                )
            await db.commit()

    def _parse(self, row: dict) -> dict:
        row["tools_enabled"] = json.loads(row.get("tools_enabled") or "[]")
        row["is_builtin"] = bool(row["is_builtin"])
        return row

    async def list_products(self) -> list[dict]:
        async with aiosqlite.connect(self.db_path) as db:
            db.row_factory = aiosqlite.Row
            cursor = await db.execute(
                "SELECT * FROM products ORDER BY is_builtin DESC, created_at ASC"
            )
            return [self._parse(dict(r)) for r in await cursor.fetchall()]

    async def get_product(self, product_id: str) -> dict | None:
        async with aiosqlite.connect(self.db_path) as db:
            db.row_factory = aiosqlite.Row
            cursor = await db.execute(
                "SELECT * FROM products WHERE id = ?", (product_id,)
            )
            row = await cursor.fetchone()
            return self._parse(dict(row)) if row else None

    async def create_product(self, data: dict) -> dict:
        product_id = data.get("id") or str(uuid.uuid4())[:8]
        now = datetime.now().isoformat()
        async with aiosqlite.connect(self.db_path) as db:
            await db.execute(
                """INSERT INTO products
                   (id, name, description, icon, system_prompt, tools_enabled,
                    preferred_provider, preferred_model, is_builtin, created_at)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, 0, ?)""",
                (
                    product_id, data["name"],
                    data.get("description", ""),
                    data.get("icon", "🤖"),
                    data.get("system_prompt"),
                    json.dumps(data.get("tools_enabled", [])),
                    data.get("preferred_provider", "auto"),
                    data.get("preferred_model", "auto"),
                    now,
                ),
            )
            await db.commit()
        return await self.get_product(product_id)

    async def delete_product(self, product_id: str):
        async with aiosqlite.connect(self.db_path) as db:
            await db.execute(
                "DELETE FROM products WHERE id = ? AND is_builtin = 0", (product_id,)
            )
            await db.commit()


product_store = ProductStore()
