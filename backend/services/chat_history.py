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
        """Veritabanı tablolarını oluştur ve migration uygula."""
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
            await self._migrate_sessions_user_columns(db)
            await db.commit()

    async def _migrate_sessions_user_columns(self, db: aiosqlite.Connection) -> None:
        """Eski DB'lerde sessions tablosuna user_id, browser_id, pinned sütunlarını ekler."""
        cursor = await db.execute("PRAGMA table_info(sessions)")
        columns = {row[1] for row in await cursor.fetchall()}
        if "user_id" not in columns:
            await db.execute("ALTER TABLE sessions ADD COLUMN user_id TEXT")
            await db.execute("CREATE INDEX IF NOT EXISTS idx_sessions_user_id ON sessions(user_id)")
        if "browser_id" not in columns:
            await db.execute("ALTER TABLE sessions ADD COLUMN browser_id TEXT")
            await db.execute("CREATE INDEX IF NOT EXISTS idx_sessions_browser_id ON sessions(browser_id)")
        if "pinned" not in columns:
            await db.execute("ALTER TABLE sessions ADD COLUMN pinned INTEGER NOT NULL DEFAULT 0")

    async def create_session(
        self,
        title: str = "Yeni Sohbet",
        product: str = "forge",
        user_id: str | None = None,
        browser_id: str | None = None,
    ) -> str:
        """Yeni bir sohbet oturumu oluştur."""
        session_id = str(uuid.uuid4())
        now = datetime.now().isoformat()
        async with aiosqlite.connect(self.db_path) as db:
            await db.execute(
                """
                INSERT INTO sessions (id, title, product, user_id, browser_id, created_at, updated_at)
                VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                (session_id, title, product, user_id, browser_id, now, now),
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

    async def get_sessions(
        self,
        product: str | None = None,
        user_id: str | None = None,
        browser_id: str | None = None,
    ) -> list[dict]:
        """Sohbet oturumlarını listele.

        - user_id verilirse: yalnızca o kullanıcıya ait sohbetler.
        - user_id yok, browser_id varsa: yalnızca user_id'si NULL olan ve o
          browser_id ile eşleşen anonim sohbetler.
        - İkisi de yoksa: yalnızca anonim ve sahipsiz sohbetler (geriye dönük
          güvenlik için browser_id'siz olanları gizleyelim).
        """
        clauses = []
        params: list = []
        if user_id is not None:
            clauses.append("user_id = ?")
            params.append(user_id)
        else:
            clauses.append("user_id IS NULL")
            if browser_id is not None:
                clauses.append("browser_id = ?")
                params.append(browser_id)
            else:
                # Eski/legacy oturumları (browser_id NULL) anonim listede gösterelim.
                clauses.append("browser_id IS NULL")
        if product:
            clauses.append("product = ?")
            params.append(product)

        sql = f"SELECT * FROM sessions WHERE {' AND '.join(clauses)} ORDER BY pinned DESC, updated_at DESC"
        async with aiosqlite.connect(self.db_path) as db:
            db.row_factory = aiosqlite.Row
            cursor = await db.execute(sql, params)
            rows = await cursor.fetchall()
            return [dict(row) for row in rows]

    async def get_session(self, session_id: str) -> dict | None:
        """Tek bir oturumu (ve sahiplik bilgilerini) getir."""
        async with aiosqlite.connect(self.db_path) as db:
            db.row_factory = aiosqlite.Row
            cursor = await db.execute("SELECT * FROM sessions WHERE id = ?", (session_id,))
            row = await cursor.fetchone()
            return dict(row) if row else None

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

    async def set_pinned(self, session_id: str, pinned: bool) -> None:
        async with aiosqlite.connect(self.db_path) as db:
            await db.execute(
                "UPDATE sessions SET pinned = ? WHERE id = ?",
                (1 if pinned else 0, session_id),
            )
            await db.commit()

    async def claim_anonymous_sessions(self, user_id: str, browser_id: str) -> int:
        """Bir browser_id'ye ait anonim sohbetleri kullanıcıya bağla. Bağlanan sayıyı döner."""
        async with aiosqlite.connect(self.db_path) as db:
            cursor = await db.execute(
                "UPDATE sessions SET user_id = ? WHERE browser_id = ? AND user_id IS NULL",
                (user_id, browser_id),
            )
            await db.commit()
            return cursor.rowcount or 0


# Global instance
chat_history = ChatHistory()
