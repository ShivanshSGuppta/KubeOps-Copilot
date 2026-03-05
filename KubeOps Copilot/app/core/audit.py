from __future__ import annotations

import os
import sqlite3
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any

@dataclass(frozen=True)
class AuditEvent:
    ts: str
    route: str
    user_agent: str
    prompt: str
    action: str
    status: str
    details: str

class AuditLog:
    def __init__(self, db_path: str) -> None:
        os.makedirs(os.path.dirname(db_path), exist_ok=True)
        self.db_path = db_path
        self._init_db()

    def _init_db(self) -> None:
        with sqlite3.connect(self.db_path) as conn:
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS audit_log (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    ts TEXT NOT NULL,
                    route TEXT NOT NULL,
                    user_agent TEXT,
                    prompt TEXT,
                    action TEXT,
                    status TEXT,
                    details TEXT
                )
                """
            )
            conn.commit()

    def write(self, event: AuditEvent) -> None:
        with sqlite3.connect(self.db_path) as conn:
            conn.execute(
                "INSERT INTO audit_log(ts, route, user_agent, prompt, action, status, details) VALUES (?, ?, ?, ?, ?, ?, ?)",
                (event.ts, event.route, event.user_agent, event.prompt, event.action, event.status, event.details),
            )
            conn.commit()

    def tail(self, limit: int = 200) -> list[dict[str, Any]]:
        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            rows = conn.execute(
                "SELECT id, ts, route, user_agent, prompt, action, status, details FROM audit_log ORDER BY id DESC LIMIT ?",
                (limit,),
            ).fetchall()
        return [dict(r) for r in rows]

def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")
