"""통계 집계 → CSV 4종 (설계 DES-S3, FR-05·AC-05).

수치는 aggregate.collect 결과를 그대로 직렬화한다 — 재계산하지 않는다.
"""

from __future__ import annotations

import csv
from datetime import datetime
from pathlib import Path


def _write(path: Path, header: list[str], rows) -> Path:
    with open(path, "w", newline="", encoding="utf-8-sig") as fh:
        w = csv.writer(fh)
        w.writerow(header)
        w.writerows(rows)
    return path


def export_stats_csv(stats: dict, out_dir: str | Path) -> list[Path]:
    """[combos, latest_decks, pick_rates, records] 순서로 경로를 반환한다."""
    out = Path(out_dir)
    out.mkdir(parents=True, exist_ok=True)
    date = datetime.now().strftime("%Y%m%d")
    return [
        _write(out / f"stats_combos_{date}.csv",
               ["generals", "win", "draw", "lose", "n", "winrate"],
               [["+".join(c["display"]), c["win"], c["draw"], c["lose"],
                 c["n"], f"{c['winrate']:.3f}"] for c in stats["combos"]]),
        _write(out / f"stats_latest_decks_{date}.csv",
               ["user_id", "user", "last_battle_time", "deck", "levels",
                "history"],
               [[d["user_id"], d["display"], d["last_battle_time"],
                 "+".join(d["deck_display"]),
                 "+".join(str(d["levels"].get(g) or "?") for g in d["deck"]),
                 " | ".join(f"{t}: {'+'.join(names)}"
                            for t, names in d["history"])]
                for d in stats["latest_decks"]]),
        _write(out / f"stats_pick_rates_{date}.csv",
               ["general_id", "general", "total", "attack", "defend", "share"],
               [[p["general_id"], p["display"], p["total"], p["attack"],
                 p["defend"], f"{p['share']:.3f}"] for p in stats["pick_rates"]]),
        _write(out / f"stats_records_{date}.csv",
               ["user_id", "user", "win", "draw", "lose", "last_battle_time"],
               [[r["user_id"], r["display"], r["win"], r["draw"], r["lose"],
                 r["last_battle_time"]] for r in stats["records"]]),
    ]
