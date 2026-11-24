import json
import sqlite3
from contextlib import closing
from datetime import datetime
from pathlib import Path

STATUSES = ["可送簽", "待廠商補件", "內部處理", "主檔維護", "系統失敗", "已寄補件", "送簽中", "已結案"]

SCHEMA = """
CREATE TABLE IF NOT EXISTS cases (
    id TEXT PRIMARY KEY,
    pic TEXT NOT NULL,
    base TEXT NOT NULL,
    po_no TEXT,
    vendor TEXT,
    outcome TEXT,
    status TEXT NOT NULL,
    folder TEXT NOT NULL,
    note TEXT DEFAULT '',
    created TEXT NOT NULL,
    updated TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS history (
    case_id TEXT NOT NULL,
    at TEXT NOT NULL,
    status TEXT NOT NULL,
    note TEXT DEFAULT ''
);
"""


class DB:
    """每次操作各開一條連線：API 請求在多個執行緒同時進來，sqlite3 連線不能跨執行緒共用。"""

    def __init__(self, path: Path):
        path.parent.mkdir(parents=True, exist_ok=True)
        self.path = path
        with closing(self._connect()) as c:
            c.executescript(SCHEMA)

    def _connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.path, timeout=10)
        conn.row_factory = sqlite3.Row
        return conn

    @staticmethod
    def now() -> str:
        return datetime.now().isoformat(timespec="seconds")

    def add(self, **c):
        t = self.now()
        with closing(self._connect()) as conn, conn:
            conn.execute(
                "INSERT OR REPLACE INTO cases (id, pic, base, po_no, vendor, outcome, status, folder, created, updated)"
                " VALUES (:id, :pic, :base, :po_no, :vendor, :outcome, :status, :folder, :t, :t)", {**c, "t": t})
            conn.execute("INSERT INTO history VALUES (?, ?, ?, ?)", (c["id"], t, c["status"], "系統處理"))

    def set_status(self, case_id: str, status: str, note: str = ""):
        if status not in STATUSES:
            raise ValueError(f"狀態必須是 {STATUSES}")
        t = self.now()
        with closing(self._connect()) as conn, conn:
            cur = conn.execute("UPDATE cases SET status = ?, note = ?, updated = ? WHERE id = ?",
                               (status, note, t, case_id))
            if not cur.rowcount:
                raise KeyError(case_id)
            conn.execute("INSERT INTO history VALUES (?, ?, ?, ?)", (case_id, t, status, note))

    def list(self, pic: str | None = None, status: str | None = None) -> list[dict]:
        q, args = "SELECT * FROM cases WHERE 1=1", []
        if pic:
            q, args = q + " AND pic = ?", args + [pic]
        if status:
            q, args = q + " AND status = ?", args + [status]
        with closing(self._connect()) as conn:
            return [dict(r) for r in conn.execute(q + " ORDER BY updated DESC", args)]

    def get(self, case_id: str) -> dict | None:
        with closing(self._connect()) as conn:
            r = conn.execute("SELECT * FROM cases WHERE id = ?", (case_id,)).fetchone()
            if not r:
                return None
            c = dict(r)
            c["history"] = [dict(h) for h in conn.execute(
                "SELECT at, status, note FROM history WHERE case_id = ? ORDER BY at", (case_id,))]
        detail = Path(c["folder"]) / "case.json"
        c["detail"] = json.loads(detail.read_text(encoding="utf-8")) if detail.exists() else None
        return c
