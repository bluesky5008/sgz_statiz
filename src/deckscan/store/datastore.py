"""SQLite 수집 원장 (설계 DES-09, ADR-001).

골격 출처: map_search C:\\src\\git\\map_search\\src\\mapscan\\store\\datastore.py
(WAL·INSERT OR REPLACE 멱등·run 기록 패턴 이식, 2026-08-08. 스키마는 설계 v1의
덱 스키마로 교체).

battle_key가 내용 기반이라 재실행·재순회에도 중복이 생기지 않는다(FR-05).
"""

from __future__ import annotations

import hashlib
import sqlite3
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path

_SCHEMA = """
CREATE TABLE IF NOT EXISTS meta (
  key   TEXT PRIMARY KEY,
  value TEXT
);

CREATE TABLE IF NOT EXISTS runs (
  run_id      INTEGER PRIMARY KEY AUTOINCREMENT,
  started_at  TEXT NOT NULL,
  finished_at TEXT,
  status      TEXT NOT NULL DEFAULT 'running',
  processed   INTEGER,
  saved       INTEGER,
  failed      INTEGER
);

CREATE TABLE IF NOT EXISTS identities (
  identity_id  INTEGER PRIMARY KEY AUTOINCREMENT,
  namespace    TEXT NOT NULL,
  label        TEXT,
  label_status TEXT NOT NULL DEFAULT 'pending',
  first_seen   TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS identity_templates (
  identity_id   INTEGER NOT NULL REFERENCES identities(identity_id),
  template_path TEXT NOT NULL,
  PRIMARY KEY (identity_id, template_path)
);

CREATE TABLE IF NOT EXISTS battles (
  battle_key            TEXT PRIMARY KEY,
  run_id                INTEGER NOT NULL REFERENCES runs(run_id),
  battle_time           TEXT,
  result                TEXT,
  attacker_id           INTEGER,
  defender_id           INTEGER,
  attacker_alliance_id  INTEGER,
  defender_alliance_id  INTEGER,
  capture_path          TEXT,
  parse_status          TEXT NOT NULL DEFAULT 'ok',
  captured_at           TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS deck_slots (
  battle_key  TEXT NOT NULL REFERENCES battles(battle_key),
  side        TEXT NOT NULL CHECK (side IN ('attack', 'defend')),
  slot        INTEGER NOT NULL CHECK (slot BETWEEN 1 AND 3),
  general_id  INTEGER,
  level       INTEGER,
  troops      INTEGER,
  match_score REAL,
  crop_path   TEXT,
  PRIMARY KEY (battle_key, side, slot)
) WITHOUT ROWID;

CREATE INDEX IF NOT EXISTS idx_slots_general ON deck_slots(general_id);
"""

SCHEMA_VERSION = "1"


def _now() -> str:
    return datetime.now().astimezone().isoformat(timespec="seconds")


@dataclass
class SlotRecord:
    side: str                       # 'attack' | 'defend'
    slot: int                       # 1..3
    general_id: int | None = None
    level: int | None = None
    troops: int | None = None
    match_score: float | None = None
    crop_path: str | None = None


@dataclass
class BattleRecord:
    battle_key: str
    battle_time: str | None
    result: str | None
    attacker_id: int | None
    defender_id: int | None
    attacker_alliance_id: int | None
    defender_alliance_id: int | None
    capture_path: str | None
    parse_status: str = "ok"        # ok|partial|failed
    slots: list[SlotRecord] = field(default_factory=list)


def make_battle_key(battle_time: str | None, attacker_id: int | None,
                    defender_id: int | None, slots: list[SlotRecord]) -> str:
    """정규화 내용 해시 — 동일 전보는 재실행에도 같은 키가 재현된다.

    결정적 요소(일시·유저 ID·장수 구성)만 사용한다(DCR-003). 병력·레벨은
    OCR 판독이라 실행 컨텍스트에 따라 값이 흔들려(2026-08-09 run2 실증:
    같은 캡처가 10000/10/10011로 판독) 키에 넣으면 같은 전보가 다른 키로
    갈라져 중복 저장된다(FR-05 위반). 값 자체는 레코드에 그대로 저장된다.
    """
    parts = [battle_time or "", str(attacker_id or ""), str(defender_id or "")]
    for s in sorted(slots, key=lambda s: (s.side, s.slot)):
        parts.append(f"{s.side},{s.slot},{s.general_id or ''}")
    return hashlib.sha1("|".join(parts).encode("utf-8")).hexdigest()


def make_fallback_key(payload: bytes) -> str:
    """파싱 실패로 키 재료가 없을 때 패널 이미지 바이트로 만드는 대체 키."""
    return "img-" + hashlib.sha1(payload).hexdigest()


class DataStore:
    def __init__(self, path: str):
        if path != ":memory:":
            Path(path).parent.mkdir(parents=True, exist_ok=True)
        self._conn = sqlite3.connect(path)
        self._conn.row_factory = sqlite3.Row
        self._conn.execute("PRAGMA journal_mode=WAL")
        self._conn.executescript(_SCHEMA)
        self._conn.execute(
            "INSERT OR IGNORE INTO meta (key, value) VALUES ('schema_version', ?)",
            (SCHEMA_VERSION,))
        self._conn.commit()

    # -- runs ---------------------------------------------------------------

    def create_run(self) -> int:
        cur = self._conn.execute(
            "INSERT INTO runs (started_at) VALUES (?)", (_now(),))
        self._conn.commit()
        return cur.lastrowid

    def get_run(self, run_id: int) -> sqlite3.Row | None:
        return self._conn.execute(
            "SELECT * FROM runs WHERE run_id=?", (run_id,)).fetchone()

    def finish_run(self, run_id: int, status: str = "done", *,
                   processed: int = 0, saved: int = 0, failed: int = 0) -> None:
        self._conn.execute(
            "UPDATE runs SET status=?, finished_at=?, processed=?, saved=?, failed=?"
            " WHERE run_id=?",
            (status, _now(), processed, saved, failed, run_id))
        self._conn.commit()

    # -- identities ---------------------------------------------------------

    def create_identity(self, namespace: str, label: str | None,
                        template_path: str) -> int:
        cur = self._conn.execute(
            "INSERT INTO identities (namespace, label, first_seen) VALUES (?, ?, ?)",
            (namespace, label, _now()))
        iid = cur.lastrowid
        self._conn.execute(
            "INSERT INTO identity_templates (identity_id, template_path) VALUES (?, ?)",
            (iid, template_path))
        self._conn.commit()
        return iid

    def add_template(self, identity_id: int, template_path: str) -> None:
        self._conn.execute(
            "INSERT OR IGNORE INTO identity_templates (identity_id, template_path)"
            " VALUES (?, ?)", (identity_id, template_path))
        self._conn.commit()

    def confirm_label(self, identity_id: int, label: str) -> None:
        self._conn.execute(
            "UPDATE identities SET label=?, label_status='confirmed'"
            " WHERE identity_id=?", (label, identity_id))
        self._conn.commit()

    def pending_identities(self) -> list[sqlite3.Row]:
        return self._conn.execute(
            "SELECT * FROM identities WHERE label_status='pending'"
            " ORDER BY identity_id").fetchall()

    def iter_identities(self, namespace: str):
        yield from self._conn.execute(
            "SELECT * FROM identities WHERE namespace=? ORDER BY identity_id",
            (namespace,))

    def templates_of(self, identity_id: int) -> list[str]:
        return [r[0] for r in self._conn.execute(
            "SELECT template_path FROM identity_templates WHERE identity_id=?"
            " ORDER BY template_path", (identity_id,))]

    # -- battles ------------------------------------------------------------

    def upsert_battle(self, run_id: int, rec: BattleRecord) -> None:
        """전보 1건 + 슬롯을 원자적으로 멱등 저장한다."""
        with self._conn:
            self._conn.execute(
                "INSERT OR REPLACE INTO battles (battle_key, run_id, battle_time,"
                " result, attacker_id, defender_id, attacker_alliance_id,"
                " defender_alliance_id, capture_path, parse_status, captured_at)"
                " VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                (rec.battle_key, run_id, rec.battle_time, rec.result,
                 rec.attacker_id, rec.defender_id, rec.attacker_alliance_id,
                 rec.defender_alliance_id, rec.capture_path, rec.parse_status,
                 _now()))
            self._conn.execute(
                "DELETE FROM deck_slots WHERE battle_key=?", (rec.battle_key,))
            self._conn.executemany(
                "INSERT INTO deck_slots (battle_key, side, slot, general_id,"
                " level, troops, match_score, crop_path)"
                " VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
                [(rec.battle_key, s.side, s.slot, s.general_id, s.level,
                  s.troops, s.match_score, s.crop_path) for s in rec.slots])

    def battle_count(self) -> int:
        return self._conn.execute("SELECT COUNT(*) FROM battles").fetchone()[0]

    def slot_count(self) -> int:
        return self._conn.execute("SELECT COUNT(*) FROM deck_slots").fetchone()[0]

    def deck_rows(self):
        """내보내기·통계용 long 형식 행 (전보 × 슬롯, 라벨 조인)."""
        yield from self._conn.execute("""
            SELECT b.battle_key, b.battle_time, b.result,
                   ua.label AS attacker, ud.label AS defender,
                   aa.label AS attacker_alliance, da.label AS defender_alliance,
                   s.side, s.slot, g.label AS general, s.level, s.troops,
                   b.parse_status
            FROM battles b
            JOIN deck_slots s ON s.battle_key = b.battle_key
            LEFT JOIN identities ua ON ua.identity_id = b.attacker_id
            LEFT JOIN identities ud ON ud.identity_id = b.defender_id
            LEFT JOIN identities aa ON aa.identity_id = b.attacker_alliance_id
            LEFT JOIN identities da ON da.identity_id = b.defender_alliance_id
            LEFT JOIN identities g  ON g.identity_id  = s.general_id
            ORDER BY b.battle_time, b.battle_key, s.side, s.slot""")

    def general_latest_levels(self):
        """장수별 최신 전투 기준 레벨 (DCR-003 — 레벨은 키가 아니라 속성)."""
        yield from self._conn.execute("""
            SELECT s.general_id, g.label AS general, s.level,
                   MAX(b.battle_time) AS last_battle_time
            FROM deck_slots s
            JOIN battles b ON b.battle_key = s.battle_key
            LEFT JOIN identities g ON g.identity_id = s.general_id
            WHERE s.level IS NOT NULL AND b.battle_time IS NOT NULL
              AND s.general_id IS NOT NULL
            GROUP BY s.general_id
            ORDER BY s.general_id""")

    def battle_rows(self):
        """내보내기용 전보 1행 (라벨 조인)."""
        yield from self._conn.execute("""
            SELECT b.battle_key, b.battle_time, b.result,
                   ua.label AS attacker, ud.label AS defender,
                   aa.label AS attacker_alliance, da.label AS defender_alliance,
                   b.parse_status, b.capture_path
            FROM battles b
            LEFT JOIN identities ua ON ua.identity_id = b.attacker_id
            LEFT JOIN identities ud ON ud.identity_id = b.defender_id
            LEFT JOIN identities aa ON aa.identity_id = b.attacker_alliance_id
            LEFT JOIN identities da ON da.identity_id = b.defender_alliance_id
            ORDER BY b.battle_time, b.battle_key""")

    def iter_battles(self):
        yield from self._conn.execute(
            "SELECT * FROM battles ORDER BY battle_time, battle_key")

    # -- lifecycle ----------------------------------------------------------

    def close(self) -> None:
        self._conn.close()

    def __enter__(self) -> "DataStore":
        return self

    def __exit__(self, *exc) -> None:
        self.close()
