"""把一次运行保存到 SQLite，供进程重启后继续。"""

from __future__ import annotations

import json
import sqlite3


class RunStore:
    def __init__(self, path: str):
        self.conn = sqlite3.connect(path, check_same_thread=False)
        self.conn.execute("CREATE TABLE IF NOT EXISTS runs (id TEXT PRIMARY KEY, payload TEXT NOT NULL)")
        self.conn.commit()

    def save(self, run_id: str, payload: dict) -> None:
        self.conn.execute(
            "INSERT OR REPLACE INTO runs VALUES (?, ?)",
            (run_id, json.dumps(payload, ensure_ascii=False)),
        )
        self.conn.commit()

    def ids(self) -> list[str]:
        return [row[0] for row in self.conn.execute("SELECT id FROM runs")]

    def get(self, run_id: str) -> dict | None:
        row = self.conn.execute("SELECT payload FROM runs WHERE id=?", (run_id,)).fetchone()
        if row is None:
            return None
        return json.loads(row[0])
