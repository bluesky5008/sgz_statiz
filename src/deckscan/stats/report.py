"""통계 집계 → 단일 HTML 리포트 (설계 DES-S2, FR-05·06).

외부 리소스 없음 — 인라인 CSS·최소 정렬 JS. 수치는 aggregate 결과 그대로.
"""

from __future__ import annotations

import html as _html
from datetime import datetime

_STYLE = """
body{font-family:'Malgun Gothic',sans-serif;margin:24px;background:#f5f2ea;color:#222}
h1{font-size:1.4em} h2{font-size:1.15em;border-bottom:2px solid #b09a6a;padding-bottom:4px}
table{border-collapse:collapse;margin:8px 0 24px;background:#fff}
th,td{border:1px solid #cbbf9f;padding:4px 10px;font-size:.92em}
th{background:#e8dfc8;cursor:pointer;user-select:none}
.bar{display:inline-block;height:10px;background:#b09a6a;vertical-align:middle}
.n{color:#777;font-size:.85em} .meta{color:#555;font-size:.9em}
"""

_SORT_JS = """
document.querySelectorAll('th').forEach(function(th){th.addEventListener('click',function(){
var t=th.closest('table'),i=Array.prototype.indexOf.call(th.parentNode.children,th);
var rows=Array.prototype.slice.call(t.querySelectorAll('tbody tr'));
var asc=th.dataset.asc!=='1';th.dataset.asc=asc?'1':'0';
rows.sort(function(a,b){var x=a.children[i].textContent,y=b.children[i].textContent;
var nx=parseFloat(x),ny=parseFloat(y);
if(!isNaN(nx)&&!isNaN(ny))return asc?nx-ny:ny-nx;
return asc?x.localeCompare(y):y.localeCompare(x);});
rows.forEach(function(r){t.querySelector('tbody').appendChild(r);});});});
"""


def _e(v) -> str:
    return _html.escape(str(v if v is not None else "—"))


def _table(headers: list[str], rows: list[list[str]]) -> list[str]:
    out = ["<table><thead><tr>"]
    out += [f"<th>{_e(h)}</th>" for h in headers]
    out.append("</tr></thead><tbody>")
    for row in rows:
        out.append("<tr>" + "".join(f"<td>{c}</td>" for c in row) + "</tr>")
    out.append("</tbody></table>")
    return out


def _pct_bar(ratio: float) -> str:
    return (f"<span class='bar' style='width:{ratio * 100:.0f}px'></span> "
            f"{ratio * 100:.1f}%")


def render_report(stats: dict) -> str:
    f = stats["friendly"]
    ex = stats["excluded"]
    p = [f"<style>{_STYLE}</style>",
         "<h1>deckscan 교전 통계 리포트</h1>",
         f"<p class='meta'>생성 {datetime.now():%Y-%m-%d %H:%M} · "
         f"전보 {stats['battle_count']}건</p>",
         "<h2 id=\"overview\">개요</h2>",
         f"<p>아군 동맹: <b>{_e(f['display'])}</b>"
         + (" (지정)" if f["overridden"]
            else f" (자동 추정 — {f['battles']}전 등장 최빈)") + "</p>",
         f"<p class='meta'>제외: 일시 없음 {ex['no_time']}건(시계열 제외), "
         f"아군 측 판별 불가 {ex['no_side']}건(승률·전적 제외)</p>",
         "<h2 id=\"decks\">유저별 최신 덱</h2>"]
    p += _table(
        ["유저", "최근 전투", "덱 (최신 레벨)", "덱 변경 이력"],
        [[_e(d["display"]), _e(d["last_battle_time"]),
          " · ".join(f"{_e(n)} <span class='n'>Lv"
                     f"{_e(d['levels'].get(g) or '?')}</span>"
                     for g, n in zip(d["deck"], d["deck_display"])),
          "<br>".join(f"<span class='n'>{_e(t)}</span> "
                      + " · ".join(_e(n) for n in names)
                      for t, names in d["history"])]
         for d in stats["latest_decks"]])
    p.append("<h2 id=\"records\">유저별 전적 (아군 관점)</h2>")
    p += _table(
        ["상대 유저", "승", "무", "패", "승률", "최근 교전"],
        [[_e(r["display"]), r["win"], r["draw"], r["lose"],
          _pct_bar(r["win"] / max(1, r["win"] + r["draw"] + r["lose"])),
          _e(r["last_battle_time"])] for r in stats["records"]])
    p.append("<h2 id=\"combos\">덱 조합별 승률 (해당 조합 측 관점)</h2>")
    p += _table(
        ["조합", "승", "무", "패", "n", "승률"],
        [[" · ".join(_e(n) for n in c["display"]), c["win"], c["draw"],
          c["lose"], c["n"], _pct_bar(c["winrate"])] for c in stats["combos"]])
    p.append("<h2 id=\"picks\">장수 픽률</h2>")
    p += _table(
        ["장수", "등장", "공격", "수비", "비율"],
        [[_e(g["display"]), g["total"], g["attack"], g["defend"],
          _pct_bar(g["share"])] for g in stats["pick_rates"]])
    p.append(f"<script>{_SORT_JS}</script>")
    return "\n".join(p)
