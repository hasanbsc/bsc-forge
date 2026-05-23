"""BSC Forge — Ürün kataloğu (SQLite)."""
import json
import uuid
from datetime import datetime
import aiosqlite
from config import settings

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
