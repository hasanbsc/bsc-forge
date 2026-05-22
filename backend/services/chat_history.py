"""BSC Forge — Sohbet Geçmişi (SQLite)

Sohbet oturumlarını ve mesajları kalıcı olarak saklar.
"""
import aiosqlite
import json
import uuid
from datetime import datetime
from pathlib import Path

from config import settings


class ChatHistory:
    """SQLite tabanlı sohbet geçmişi yöneticisi."""

    def __init__(self):
        self.db_path = settings.DB_PATH
        # data klasörünün var olduğundan emin ol
        Path(self.db_path).parent.mkdir(parents=True, exist_ok=True)

    async def init_db(self):
        """Veritabanı tablolarını oluştur."""
        async with aiosqlite.connect(self.db_path) as db:
            await db.execute("""
                CREATE TABLE IF NOT EXISTS sessions (
                    id TEXT PRIMARY KEY,
                    title TEXT NOT NULL,
                    provider TEXT DEFAULT 'gemini',
                    model TEXT DEFAULT 'gemini-2.5-flash',
                    product TEXT DEFAULT 'forge',
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL
                )
            """)
            await db.execute("""
                CREATE TABLE IF NOT EXISTS messages (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    session_id TEXT NOT NULL,
                    role TEXT NOT NULL,
                    content TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    FOREIGN KEY (session_id) REFERENCES sessions (id)
                )
            """)
            await db.commit()

    async def create_session(self, title: str = "Yeni Sohbet", product: str = "forge") -> str:
        """Yeni bir sohbet oturumu oluştur."""
        session_id = str(uuid.uuid4())
        now = datetime.now().isoformat()
        async with aiosqlite.connect(self.db_path) as db:
            await db.execute(
                "INSERT INTO sessions (id, title, product, created_at, updated_at) VALUES (?, ?, ?, ?, ?)",
                (session_id, title, product, now, now),
            )
            await db.commit()
        return session_id

    async def add_message(self, session_id: str, role: str, content: str):
        """Bir oturuma mesaj ekle."""
        now = datetime.now().isoformat()
        async with aiosqlite.connect(self.db_path) as db:
            await db.execute(
                "INSERT INTO messages (session_id, role, content, created_at) VALUES (?, ?, ?, ?)",
                (session_id, role, content, now),
            )
            await db.execute(
                "UPDATE sessions SET updated_at = ? WHERE id = ?",
                (now, session_id),
            )
            await db.commit()

    async def get_messages(self, session_id: str) -> list[dict]:
        """Bir oturumun tüm mesajlarını getir."""
        async with aiosqlite.connect(self.db_path) as db:
            db.row_factory = aiosqlite.Row
            cursor = await db.execute(
                "SELECT role, content, created_at FROM messages WHERE session_id = ? ORDER BY id ASC",
                (session_id,),
            )
            rows = await cursor.fetchall()
            return [{"role": row["role"], "content": row["content"], "created_at": row["created_at"]} for row in rows]

    async def get_sessions(self, product: str | None = None) -> list[dict]:
        """Tüm sohbet oturumlarını listele."""
        async with aiosqlite.connect(self.db_path) as db:
            db.row_factory = aiosqlite.Row
            if product:
                cursor = await db.execute(
                    "SELECT * FROM sessions WHERE product = ? ORDER BY updated_at DESC",
                    (product,),
                )
            else:
                cursor = await db.execute("SELECT * FROM sessions ORDER BY updated_at DESC")
            rows = await cursor.fetchall()
            return [dict(row) for row in rows]

    async def update_session_title(self, session_id: str, title: str):
        """Oturum başlığını güncelle."""
        async with aiosqlite.connect(self.db_path) as db:
            await db.execute(
                "UPDATE sessions SET title = ?, updated_at = ? WHERE id = ?",
                (title, datetime.now().isoformat(), session_id),
            )
            await db.commit()

    async def delete_session(self, session_id: str):
        """Bir oturumu ve tüm mesajlarını sil."""
        async with aiosqlite.connect(self.db_path) as db:
            await db.execute("DELETE FROM messages WHERE session_id = ?", (session_id,))
            await db.execute("DELETE FROM sessions WHERE id = ?", (session_id,))
            await db.commit()


# Global instance
chat_history = ChatHistory()
