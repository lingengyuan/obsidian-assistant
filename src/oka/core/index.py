from __future__ import annotations

import json
import sqlite3
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, Iterable, Optional

SCHEMA_VERSION = 1


@dataclass
class CacheRecord:
    path: str
    mtime: float
    size: int
    sha256: str
    frontmatter: str
    frontmatter_keys: str
    links: str
    top_terms: str


class IndexStore:
    def __init__(self, db_path: Path) -> None:
        self.db_path = db_path
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self.conn = sqlite3.connect(self.db_path)
        self.conn.row_factory = sqlite3.Row
        self._init_schema()

    def _init_schema(self) -> None:
        cur = self.conn.cursor()
        version = cur.execute("PRAGMA user_version").fetchone()[0]
        if version != SCHEMA_VERSION:
            cur.execute("DROP TABLE IF EXISTS files")
            cur.execute("DROP TABLE IF EXISTS meta")
        cur.execute(
            "CREATE TABLE IF NOT EXISTS meta (key TEXT PRIMARY KEY, value TEXT)"
        )
        cur.execute(
            """
            CREATE TABLE IF NOT EXISTS files (
                path TEXT PRIMARY KEY,
                mtime REAL NOT NULL,
                size INTEGER NOT NULL,
                sha256 TEXT NOT NULL,
                frontmatter TEXT,
                frontmatter_keys TEXT,
                links TEXT,
                top_terms TEXT
            )
            """
        )
        cur.execute(f"PRAGMA user_version = {SCHEMA_VERSION}")
        self.conn.commit()

    def get(self, path: str) -> Optional[Dict[str, object]]:
        cur = self.conn.cursor()
        row = cur.execute(
            "SELECT path, mtime, size, sha256, frontmatter, frontmatter_keys, links, top_terms FROM files WHERE path=?",
            (path,),
        ).fetchone()
        return dict(row) if row else None

    def upsert(self, record: CacheRecord) -> None:
        cur = self.conn.cursor()
        cur.execute(
            """
            INSERT INTO files (path, mtime, size, sha256, frontmatter, frontmatter_keys, links, top_terms)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(path) DO UPDATE SET
                mtime=excluded.mtime,
                size=excluded.size,
                sha256=excluded.sha256,
                frontmatter=excluded.frontmatter,
                frontmatter_keys=excluded.frontmatter_keys,
                links=excluded.links,
                top_terms=excluded.top_terms
            """,
            (
                record.path,
                record.mtime,
                record.size,
                record.sha256,
                record.frontmatter,
                record.frontmatter_keys,
                record.links,
                record.top_terms,
            ),
        )

    def remove_missing(self, paths: Iterable[str]) -> int:
        current = set(paths)
        cur = self.conn.cursor()
        existing = {row[0] for row in cur.execute("SELECT path FROM files").fetchall()}
        missing = existing - current
        if not missing:
            return 0
        cur.executemany("DELETE FROM files WHERE path=?", [(path,) for path in missing])
        return len(missing)

    def commit(self) -> None:
        self.conn.commit()

    def close(self) -> None:
        self.conn.close()


def encode_json(value: object) -> str:
    return json.dumps(value, ensure_ascii=False)


def decode_json(value: Optional[str], default: object) -> object:
    if not value:
        return default
    try:
        return json.loads(value)
    except json.JSONDecodeError:
        return default
