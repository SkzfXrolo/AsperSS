"""Capa de base de datos del bot.

Usa psycopg2 con un pool sencillo y context manager para cursors.
Comparte la misma BD Postgres que el web app, pero las tablas del bot
viven en su propio namespace (prefijo `bot_`).
"""
from __future__ import annotations

import logging
import threading
from contextlib import contextmanager
from pathlib import Path
from typing import Iterator

import psycopg2
from psycopg2.extras import RealDictCursor
from psycopg2.pool import ThreadedConnectionPool

from . import config

log = logging.getLogger("bot.db")

_pool: ThreadedConnectionPool | None = None
_pool_lock = threading.Lock()


def init_pool(min_conn: int = 1, max_conn: int = 8) -> None:
    """Inicializa el pool de conexiones (idempotente)."""
    global _pool
    with _pool_lock:
        if _pool is not None:
            return
        _pool = ThreadedConnectionPool(
            min_conn,
            max_conn,
            config.DATABASE_URL,
            cursor_factory=RealDictCursor,
            connect_timeout=10,
        )
        log.info("[DB] Pool inicializado (%d-%d conexiones)", min_conn, max_conn)


def close_pool() -> None:
    global _pool
    with _pool_lock:
        if _pool is not None:
            _pool.closeall()
            _pool = None
            log.info("[DB] Pool cerrado")


@contextmanager
def cursor(commit: bool = True) -> Iterator[psycopg2.extensions.cursor]:
    """Context manager que entrega un cursor RealDictCursor.

    Uso:
        with db.cursor() as cur:
            cur.execute("SELECT ...")
            row = cur.fetchone()
    """
    if _pool is None:
        init_pool()
    assert _pool is not None
    conn = _pool.getconn()
    try:
        cur = conn.cursor()
        try:
            yield cur
            if commit:
                conn.commit()
        except Exception:
            conn.rollback()
            raise
        finally:
            cur.close()
    finally:
        _pool.putconn(conn)


def apply_schema() -> None:
    """Aplica bot/schema.sql (idempotente). Se llama al arrancar."""
    schema_path = Path(__file__).resolve().parent / "schema.sql"
    if not schema_path.exists():
        log.warning("[DB] schema.sql no encontrado en %s", schema_path)
        return
    sql = schema_path.read_text(encoding="utf-8")
    with cursor() as cur:
        cur.execute(sql)
    log.info("[DB] Schema aplicado desde %s", schema_path.name)


# ── Helpers de alto nivel ─────────────────────────────────────────────────

def get_setting(guild_id: int, key: str, default: str | None = None) -> str | None:
    with cursor() as cur:
        cur.execute(
            "SELECT value FROM bot_settings WHERE guild_id = %s AND key = %s",
            (guild_id, key),
        )
        row = cur.fetchone()
        return row["value"] if row else default


def set_setting(guild_id: int, key: str, value: str | None) -> None:
    with cursor() as cur:
        if value is None:
            cur.execute(
                "DELETE FROM bot_settings WHERE guild_id = %s AND key = %s",
                (guild_id, key),
            )
        else:
            cur.execute(
                """
                INSERT INTO bot_settings (guild_id, key, value)
                VALUES (%s, %s, %s)
                ON CONFLICT (guild_id, key) DO UPDATE SET value = EXCLUDED.value, updated_at = NOW()
                """,
                (guild_id, key, value),
            )
