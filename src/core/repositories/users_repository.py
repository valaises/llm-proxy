import sqlite3
import asyncio
from pathlib import Path

from typing import List, Dict, Optional
from functools import partial
from contextlib import contextmanager

from pydantic import BaseModel, EmailStr


class UserCreatePost(BaseModel):
    email: EmailStr


class UserUpdatePost(BaseModel):
    user_id: int
    email: EmailStr


class UserDeletePost(BaseModel):
    user_id: int


class ApiKeyListPost(BaseModel):
    user_id: Optional[int] = None


class ApiKeyCreatePost(BaseModel):
    api_key: Optional[str] = None
    scope: str
    user_id: int


class ApiKeyUpdatePost(BaseModel):
    api_key: str
    user_id: int
    scope: Optional[str] = None


class ApiKeyDeletePost(BaseModel):
    api_key: str
    user_id: int


class UsersRepository:
    def __init__(
            self,
            db_path: Path
    ):
        self.db_path = db_path
        # Run init_db synchronously since it's called only once during startup
        self._init_db()

    @contextmanager
    def _get_db_connection(self):
        conn = sqlite3.connect(self.db_path)
        try:
            yield conn
        finally:
            conn.close()

    def _init_db(self):
        """Initialize SQLite database and create tables if not exists."""
        with self._get_db_connection() as conn:
            # Create users table
            conn.execute("""
                CREATE TABLE IF NOT EXISTS users (
                    user_id INTEGER PRIMARY KEY AUTOINCREMENT,
                    email TEXT NOT NULL UNIQUE,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)

            # Create api_keys table with foreign key to users
            conn.execute("""
                CREATE TABLE IF NOT EXISTS api_keys (
                    api_key TEXT PRIMARY KEY,
                    user_id INTEGER NOT NULL,
                    scope TEXT NOT NULL,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (user_id) REFERENCES users(user_id) ON DELETE CASCADE
                )
            """)
            conn.commit()

    async def _run_in_thread(self, func, *args):
        """Run a blocking function in a thread pool."""
        loop = asyncio.get_running_loop()
        return await loop.run_in_executor(None, partial(func, *args))

    def _list_users_sync(self) -> List[Dict]:
        with self._get_db_connection() as conn:
            cursor = conn.execute("SELECT user_id, email, created_at FROM users")
            return [
                {
                    "user_id": row[0],
                    "email": row[1],
                    "created_at": row[2]
                }
                for row in cursor.fetchall()
            ]

    def _create_user_sync(self, post: UserCreatePost) -> Optional[Dict]:
        with self._get_db_connection() as conn:
            try:
                cursor = conn.execute(
                    "INSERT INTO users (email) VALUES (?) RETURNING user_id, email, created_at",
                    (post.email,)
                )
                row = cursor.fetchone()
                conn.commit()
                if row:
                    return {
                        "user_id": row[0],
                        "email": row[1],
                        "created_at": row[2]
                    }
                return None
            except sqlite3.IntegrityError:
                return None

    def _update_user_sync(self, post: UserUpdatePost) -> Optional[Dict]:
        with self._get_db_connection() as conn:
            try:
                cursor = conn.execute(
                    """UPDATE users SET email = ? 
                       WHERE user_id = ? 
                       RETURNING user_id, email, created_at""",
                    (post.email, post.user_id)
                )
                row = cursor.fetchone()
                conn.commit()
                if row:
                    return {
                        "user_id": row[0],
                        "email": row[1],
                        "created_at": row[2]
                    }
                return None
            except sqlite3.IntegrityError:
                return None

    def _delete_user_sync(self, post: UserDeletePost) -> bool:
        with self._get_db_connection() as conn:
            cursor = conn.execute(
                "DELETE FROM users WHERE user_id = ?",
                (post.user_id,)
            )
            conn.commit()
            return cursor.rowcount > 0

    def _list_keys_sync(self, post: ApiKeyListPost) -> List[Dict]:
        with self._get_db_connection() as conn:
            query = """
                SELECT k.api_key, k.scope, k.created_at, u.user_id, u.email 
                FROM api_keys k
                JOIN users u ON k.user_id = u.user_id
            """
            params = []

            if post.user_id is not None:
                query += " WHERE k.user_id = ?"
                params.append(post.user_id)

            cursor = conn.execute(query, params)
            return [
                {
                    "api_key": row[0],
                    "scope": row[1],
                    "created_at": row[2],
                    "user_id": row[3],
                    "user_email": row[4]
                }
                for row in cursor.fetchall()
            ]

    def _create_key_sync(self, post: ApiKeyCreatePost) -> bool:
        with self._get_db_connection() as conn:
            try:
                # First check if user exists
                cursor = conn.execute(
                    "SELECT 1 FROM users WHERE user_id = ?",
                    (post.user_id,)
                )
                if not cursor.fetchone():
                    raise ValueError("User not found")

                conn.execute(
                    "INSERT INTO api_keys (api_key, scope, user_id) VALUES (?, ?, ?)",
                    (post.api_key, post.scope, post.user_id)
                )
                conn.commit()
                return True
            except sqlite3.IntegrityError:
                return False

    def _delete_key_sync(self, post: ApiKeyDeletePost) -> bool:
        with self._get_db_connection() as conn:
            cursor = conn.execute(
                "DELETE FROM api_keys WHERE api_key = ? AND user_id = ?",
                (post.api_key, post.user_id)
            )
            conn.commit()
            return cursor.rowcount > 0

    def _update_key_sync(self, post: ApiKeyUpdatePost) -> bool:
        if not post.scope:
            raise ValueError("No updates provided")

        with self._get_db_connection() as conn:
            cursor = conn.execute(
                "UPDATE api_keys SET scope = ? WHERE api_key = ? AND user_id = ?",
                (post.scope, post.api_key, post.user_id)
            )
            conn.commit()
            return cursor.rowcount > 0

    async def list_users(self) -> List[Dict]:
        return await self._run_in_thread(self._list_users_sync)

    async def create_user(self, post: UserCreatePost) -> Optional[Dict]:
        return await self._run_in_thread(self._create_user_sync, post)

    async def update_user(self, post: UserUpdatePost) -> Optional[Dict]:
        return await self._run_in_thread(self._update_user_sync, post)

    async def delete_user(self, post: UserDeletePost) -> bool:
        return await self._run_in_thread(self._delete_user_sync, post)

    async def list_keys(self, post: ApiKeyListPost) -> List[Dict]:
        return await self._run_in_thread(self._list_keys_sync, post)

    async def create_key(self, post: ApiKeyCreatePost) -> bool:
        return await self._run_in_thread(self._create_key_sync, post)

    async def delete_key(self, post: ApiKeyDeletePost) -> bool:
        return await self._run_in_thread(self._delete_key_sync, post)

    async def update_key(self, post: ApiKeyUpdatePost) -> bool:
        return await self._run_in_thread(self._update_key_sync, post)
