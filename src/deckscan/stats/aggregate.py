"""교전 통계 집계 (설계 DES-S1, FR-01~04·06) — 수집 DB(읽기 전용) → 통계.

모든 수치의 유일한 원천이다 — HTML·CSV는 이 결과를 직렬화만 한다(AC-05).
관점 정규화(A-01): battles.result는 아군 관점이므로, 아군 동맹이 속한 측을
판별해 공격/수비 측의 승·무·패로 변환한다. 아군 동맹은 기본적으로 전투
등장 횟수 최빈 동맹으로 추정하고 --alliance로 재정의한다.
"""

from __future__ import annotations

import sqlite3
from collections import Counter, defaultdict

_OUTCOME = {"승": "win", "무": "draw", "패": "lose"}


def _display_names(conn: sqlite3.Connection) -> dict[int, str]:
    """식별자 표기(FR-06): 확정 라벨 그대로, 미확정은 `#ID(제안값)`."""
    names: dict[int, str] = {}
    for r in conn.execute("SELECT identity_id, label, label_status FROM identities"):
        iid, label, status = r
        names[iid] = label if status == "confirmed" and label \
            else f"#{iid}({label or '?'})"
    return names


def _friendly(conn: sqlite3.Connection, battles: list[sqlite3.Row],
              names: dict[int, str], alliance: str | None) -> dict:
    """아군 동맹 판별(A-01). override는 라벨(확정/제안) 또는 숫자 ID 문자열."""
    if alliance is not None:
        for r in conn.execute(
                "SELECT identity_id, label FROM identities WHERE namespace='alliance'"):
            if alliance in (str(r[0]), r[1]):
                return {"alliance_id": r[0], "display": names.get(r[0], str(r[0])),
                        "battles": None, "overridden": True}
        raise ValueError(f"동맹을 찾을 수 없습니다: {alliance}")
    seen = Counter()
    for b in battles:
        for aid in {b["attacker_alliance_id"], b["defender_alliance_id"]}:
            if aid is not None:
                seen[aid] += 1
    if not seen:
        return {"alliance_id": None, "display": None, "battles": 0,
                "overridden": False}
    top, count = seen.most_common(1)[0]
    return {"alliance_id": top, "display": names.get(top, str(top)),
            "battles": count, "overridden": False}


def _side_of(battle: sqlite3.Row, friendly_id: int | None) -> str | None:
    """아군 동맹이 속한 측('attack'/'defend'). 불명·양측이면 None."""
    att, dfd = battle["attacker_alliance_id"], battle["defender_alliance_id"]
    if friendly_id is None or att == dfd:
        return None
    if att == friendly_id:
        return "attack"
    if dfd == friendly_id:
        return "defend"
    return None


def collect(conn: sqlite3.Connection, alliance: str | None = None) -> dict:
    """통계 4종 + 메타를 계산한다. failed 레코드는 제외한다."""
    conn.row_factory = sqlite3.Row
    names = _display_names(conn)
    battles = conn.execute(
        "SELECT * FROM battles WHERE parse_status != 'failed'").fetchall()
    slots: dict[str, dict[str, list[int]]] = defaultdict(
        lambda: {"attack": [], "defend": []})
    levels: dict[int, tuple[str, int]] = {}
    for r in conn.execute(
            "SELECT s.battle_key, s.side, s.slot, s.general_id, s.level, "
            "b.battle_time FROM deck_slots s "
            "JOIN battles b ON b.battle_key = s.battle_key "
            "ORDER BY s.battle_key, s.side, s.slot"):
        if r["general_id"] is not None:
            slots[r["battle_key"]][r["side"]].append(r["general_id"])
            if r["level"] is not None and r["battle_time"] is not None:
                prev = levels.get(r["general_id"])
                if prev is None or r["battle_time"] >= prev[0]:
                    levels[r["general_id"]] = (r["battle_time"], r["level"])
    latest_levels = {gid: lv for gid, (_, lv) in levels.items()}

    friendly = _friendly(conn, battles, names, alliance)
    fid = friendly["alliance_id"]
    excluded = {"no_time": 0, "no_side": 0}

    pick = defaultdict(lambda: {"total": 0, "attack": 0, "defend": 0})
    combos: dict[tuple, dict] = defaultdict(
        lambda: {"win": 0, "draw": 0, "lose": 0})
    records: dict[int, dict] = defaultdict(
        lambda: {"win": 0, "draw": 0, "lose": 0, "last_battle_time": None})
    per_user: dict[int, list] = defaultdict(list)
    total_slots = 0

    for b in battles:
        deck = slots[b["battle_key"]]
        for side in ("attack", "defend"):
            for gid in deck[side]:
                pick[gid]["total"] += 1
                pick[gid][side] += 1
                total_slots += 1
        if b["battle_time"] is None:
            excluded["no_time"] += 1
        else:
            for side, user_key in (("attack", "attacker_id"),
                                   ("defend", "defender_id")):
                if b[user_key] is not None and deck[side]:
                    per_user[b[user_key]].append(
                        (b["battle_time"], tuple(deck[side])))
        side = _side_of(b, fid)
        outcome = _OUTCOME.get(b["result"])
        if side is None or outcome is None:
            excluded["no_side"] += 1
            continue
        enemy_side = "defend" if side == "attack" else "attack"
        flipped = {"win": "lose", "lose": "win", "draw": "draw"}[outcome]
        for s, oc in ((side, outcome), (enemy_side, flipped)):
            if len(deck[s]) == 3:
                combos[tuple(sorted(deck[s]))][oc] += 1
        opponent = b["attacker_id"] if side == "defend" else b["defender_id"]
        if opponent is not None:
            rec = records[opponent]
            rec[outcome] += 1
            if b["battle_time"] is not None and \
                    (rec["last_battle_time"] is None
                     or b["battle_time"] > rec["last_battle_time"]):
                rec["last_battle_time"] = b["battle_time"]

    latest_decks = []
    for uid, entries in per_user.items():
        entries.sort()
        history = []
        for t, deck_t in entries:
            key = tuple(sorted(deck_t))
            if not history or key != history[-1][1]:
                history.append((t, key))
        last_t, last_deck = entries[-1]
        latest_decks.append({
            "user_id": uid, "display": names.get(uid, str(uid)),
            "last_battle_time": last_t, "deck": list(last_deck),
            "deck_display": [names.get(g, str(g)) for g in last_deck],
            "levels": {g: latest_levels.get(g) for g in last_deck},
            "history": [(t, [names.get(g, str(g)) for g in k])
                        for t, k in history],
        })
    latest_decks.sort(key=lambda d: d["last_battle_time"], reverse=True)

    pick_rates = [{"general_id": g, "display": names.get(g, str(g)),
                   "share": (v["total"] / total_slots) if total_slots else 0.0,
                   **v} for g, v in pick.items()]
    pick_rates.sort(key=lambda p: (-p["total"], p["general_id"]))

    combo_rows = []
    for generals, v in combos.items():
        n = v["win"] + v["draw"] + v["lose"]
        combo_rows.append({
            "generals": generals,
            "display": [names.get(g, str(g)) for g in generals],
            "n": n, "winrate": (v["win"] / n) if n else 0.0, **v})
    combo_rows.sort(key=lambda c: (-c["n"], -c["winrate"]))

    record_rows = [{"user_id": u, "display": names.get(u, str(u)), **v}
                   for u, v in records.items()]
    record_rows.sort(key=lambda r: -(r["win"] + r["draw"] + r["lose"]))

    return {"friendly": friendly, "names": names, "excluded": excluded,
            "battle_count": len(battles), "latest_decks": latest_decks,
            "pick_rates": pick_rates, "combos": combo_rows,
            "records": record_rows}
