"""Annuaire et journal d'audit du portail (SQLite local, aucun message n'y figure)."""
from __future__ import annotations

import sqlite3
import threading
import time

SCHEMA = """
CREATE TABLE IF NOT EXISTS agents (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  username TEXT NOT NULL UNIQUE,
  full_name TEXT NOT NULL,
  ministere TEXT NOT NULL,
  fonction TEXT NOT NULL,
  role TEXT NOT NULL,
  kc_id TEXT NOT NULL,
  mxid TEXT NOT NULL,
  status TEXT NOT NULL DEFAULT 'actif',
  created_at INTEGER NOT NULL,
  revoked_at INTEGER
);
CREATE TABLE IF NOT EXISTS audit (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  ts INTEGER NOT NULL,
  actor TEXT NOT NULL,
  action TEXT NOT NULL,
  target TEXT NOT NULL,
  detail TEXT NOT NULL DEFAULT ''
);
CREATE TABLE IF NOT EXISTS channels (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  room_id TEXT NOT NULL,
  name TEXT NOT NULL,
  niveau TEXT NOT NULL,
  ministere TEXT NOT NULL,
  owner TEXT NOT NULL,
  members INTEGER NOT NULL,
  created_at INTEGER NOT NULL
);
"""


class Database:
    def __init__(self, path: str) -> None:
        self.conn = sqlite3.connect(path, check_same_thread=False)
        self.conn.row_factory = sqlite3.Row
        self.lock = threading.Lock()
        with self.lock:
            self.conn.executescript(SCHEMA)
            self.conn.commit()

    def execute(self, sql: str, params: tuple = ()) -> sqlite3.Cursor:
        with self.lock:
            cur = self.conn.execute(sql, params)
            self.conn.commit()
            return cur

    def query(self, sql: str, params: tuple = ()) -> list[sqlite3.Row]:
        with self.lock:
            return self.conn.execute(sql, params).fetchall()

    def one(self, sql: str, params: tuple = ()) -> sqlite3.Row | None:
        rows = self.query(sql, params)
        return rows[0] if rows else None

    def audit(self, actor: str, action: str, target: str, detail: str = "") -> None:
        self.execute("INSERT INTO audit (ts, actor, action, target, detail) VALUES (?,?,?,?,?)",
                     (int(time.time()), actor, action, target, detail))
