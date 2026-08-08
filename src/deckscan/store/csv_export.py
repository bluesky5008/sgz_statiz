"""CSV 내보내기 (설계 §CSV 내보내기 계약, ADR-001).

규약 출처: map_search C:\\src\\git\\map_search\\src\\mapscan\\store\\csv_export.py
(UTF-8 BOM 이식, 2026-08-09. 원본의 분할 저장은 전보 규모(수백 건)에 불필요해
제외). battles_<날짜>.csv는 전보 1행, deck_long_<날짜>.csv는 장수 1행(피벗
집계용 long 형식)이다.
"""

from __future__ import annotations

import csv
from datetime import datetime
from pathlib import Path

from .datastore import DataStore

BATTLES_HEADER = ["battle_key", "battle_time", "result", "attacker", "defender",
                  "attacker_alliance", "defender_alliance", "parse_status",
                  "capture_path"]
DECK_HEADER = ["battle_key", "battle_time", "result", "attacker", "defender",
               "side", "slot", "general", "level", "troops"]


def export_csv(store: DataStore, out_dir: str | Path) -> list[Path]:
    """전보·덱 CSV 2종을 생성하고 경로를 [battles, deck_long] 순서로 반환한다."""
    date = datetime.now().strftime("%Y%m%d")
    out = Path(out_dir)
    out.mkdir(parents=True, exist_ok=True)

    battles_path = out / f"battles_{date}.csv"
    with open(battles_path, "w", newline="", encoding="utf-8-sig") as fh:
        w = csv.writer(fh)
        w.writerow(BATTLES_HEADER)
        for r in store.battle_rows():
            w.writerow([r[c] for c in BATTLES_HEADER])

    deck_path = out / f"deck_long_{date}.csv"
    with open(deck_path, "w", newline="", encoding="utf-8-sig") as fh:
        w = csv.writer(fh)
        w.writerow(DECK_HEADER)
        for r in store.deck_rows():
            w.writerow([r[c] for c in DECK_HEADER])

    return [battles_path, deck_path]
