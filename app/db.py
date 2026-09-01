"""Sehr einfache SQLite-Anbindung (kein ORM) für Job-Status und Einstellungen."""
import sqlite3
import time
import os
import threading
import config

_lock = threading.Lock()


def get_conn():
    os.makedirs(os.path.dirname(config.DB_PATH), exist_ok=True)
    conn = sqlite3.connect(config.DB_PATH, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    return conn


_conn = None


def conn():
    global _conn
    if _conn is None:
        _conn = get_conn()
        init_db(_conn)
    return _conn


def init_db(c):
    c.execute(
        """
        CREATE TABLE IF NOT EXISTS jobs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            filename TEXT NOT NULL,
            status TEXT NOT NULL DEFAULT 'eingegangen',
            recognized_names TEXT DEFAULT '',
            caption TEXT DEFAULT '',
            error TEXT DEFAULT '',
            created_at REAL NOT NULL,
            processed_at REAL,
            forward_at REAL,
            sent_at REAL,
            thumb_path TEXT
        )
        """
    )
    c.execute(
        """
        CREATE TABLE IF NOT EXISTS settings (
            key TEXT PRIMARY KEY,
            value TEXT
        )
        """
    )
    c.commit()
    # Default: Automatik läuft
    if get_setting("automation_paused") is None:
        set_setting("automation_paused", "0")


def get_setting(key, default=None):
    cur = conn().execute("SELECT value FROM settings WHERE key = ?", (key,))
    row = cur.fetchone()
    return row["value"] if row else default


def set_setting(key, value):
    with _lock:
        conn().execute(
            "INSERT INTO settings (key, value) VALUES (?, ?) "
            "ON CONFLICT(key) DO UPDATE SET value = excluded.value",
            (key, str(value)),
        )
        conn().commit()


def is_automation_paused() -> bool:
    return get_setting("automation_paused", "0") == "1"


def create_job(filename: str) -> int:
    with _lock:
        cur = conn().execute(
            "INSERT INTO jobs (filename, status, created_at) VALUES (?, 'eingegangen', ?)",
            (filename, time.time()),
        )
        conn().commit()
        return cur.lastrowid


def update_job(job_id: int, **fields):
    if not fields:
        return
    with _lock:
        cols = ", ".join(f"{k} = ?" for k in fields)
        values = list(fields.values()) + [job_id]
        conn().execute(f"UPDATE jobs SET {cols} WHERE id = ?", values)
        conn().commit()


def get_job(job_id: int):
    cur = conn().execute("SELECT * FROM jobs WHERE id = ?", (job_id,))
    return cur.fetchone()


def list_jobs(limit: int = 200):
    cur = conn().execute("SELECT * FROM jobs ORDER BY created_at DESC LIMIT ?", (limit,))
    return cur.fetchall()


def list_pending_forward():
    cur = conn().execute(
        "SELECT * FROM jobs WHERE status = 'wartet_auf_versand' ORDER BY forward_at ASC"
    )
    return cur.fetchall()
