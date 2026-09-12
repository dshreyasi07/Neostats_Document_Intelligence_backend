import json
import sqlite3
from pathlib import Path

from .config import DATABASE_PATH


def get_connection():
    Path(DATABASE_PATH).parent.mkdir(parents=True, exist_ok=True)
    connection = sqlite3.connect(DATABASE_PATH)
    connection.row_factory = sqlite3.Row
    return connection


def init_db():
    with get_connection() as connection:
        connection.execute("""
            CREATE TABLE IF NOT EXISTS documents (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                document_name TEXT NOT NULL,
                document_type TEXT NOT NULL,
                processing_status TEXT NOT NULL,
                result_json TEXT NOT NULL,
                created_at TEXT NOT NULL
            )
        """)
        connection.commit()


def save_result(result):
    with get_connection() as connection:
        connection.execute(
            "INSERT INTO documents(document_name, document_type, processing_status, result_json, created_at) VALUES (?, ?, ?, ?, ?)",
            (result["document_name"], result["document_type"], result["processing_status"], json.dumps(result), result["processing_metadata"]["processed_at"]),
        )
        connection.commit()


def list_results():
    with get_connection() as connection:
        rows = connection.execute("SELECT result_json FROM documents ORDER BY id DESC").fetchall()
    return [json.loads(row["result_json"]) for row in rows]


def latest_result(document_name):
    with get_connection() as connection:
        row = connection.execute("SELECT result_json FROM documents WHERE document_name = ? ORDER BY id DESC LIMIT 1", (document_name,)).fetchone()
    return json.loads(row["result_json"]) if row else None
