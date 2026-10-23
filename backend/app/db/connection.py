import sqlite3
from contextlib import contextmanager
from pathlib import Path
from typing import Generator
from app.config import settings


def get_db_path() -> Path:
    db_path = settings.get_database_path()
    db_path.parent.mkdir(parents=True, exist_ok=True)
    return db_path


def init_db(db_path: Path = None) -> None:
    path = db_path or get_db_path()
    schema_path = Path(__file__).parent / "schema.sql"
    with open(schema_path, "r", encoding="utf-8") as f:
        schema_sql = f.read()

    conn = sqlite3.connect(str(path))
    try:
        conn.execute("PRAGMA foreign_keys = ON;")
        conn.execute("PRAGMA journal_mode = WAL;")
        conn.executescript(schema_sql)
        conn.commit()
    finally:
        conn.close()


@contextmanager
def get_connection(db_path: Path = None) -> Generator[sqlite3.Connection, None, None]:
    path = db_path or get_db_path()
    conn = sqlite3.connect(str(path))
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON;")
    try:
        yield conn
    finally:
        conn.close()


@contextmanager
def get_transaction(db_path: Path = None) -> Generator[sqlite3.Connection, None, None]:
    with get_connection(db_path) as conn:
        try:
            conn.execute("BEGIN TRANSACTION")
            yield conn
            conn.commit()
        except Exception:
            conn.rollback()
            raise
