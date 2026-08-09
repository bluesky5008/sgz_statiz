"""TASK-S3~S5 선행 테스트 — 통계 CSV·HTML 리포트·CLI (FR-05·06, AC-01·05·06)."""

import sqlite3
import tempfile
import unittest
from pathlib import Path

from deckscan.stats.aggregate import collect
from deckscan.stats.csv_out import export_stats_csv
from deckscan.stats.report import render_report
from tests.test_stats import build_fixture


class _Base(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tmp = tempfile.TemporaryDirectory()
        cls.db = str(Path(cls.tmp.name) / "s.db")
        cls.ids = build_fixture(cls.db)
        conn = sqlite3.connect(f"file:{cls.db}?mode=ro", uri=True)
        cls.stats = collect(conn)
        conn.close()

    @classmethod
    def tearDownClass(cls):
        cls.tmp.cleanup()


class StatsCsvTest(_Base):
    def test_four_files_with_matching_numbers(self):
        out = Path(self.tmp.name) / "csv"
        paths = export_stats_csv(self.stats, out)
        names = sorted(p.name for p in paths)
        self.assertEqual(len(paths), 4)
        for prefix, name in zip(("stats_combos_", "stats_latest_decks_",
                                 "stats_pick_rates_", "stats_records_"), names):
            self.assertTrue(name.startswith(prefix), name)
        for p in paths:
            self.assertEqual(p.read_bytes()[:3], b"\xef\xbb\xbf")   # BOM
        combos = [p for p in paths if p.name.startswith("stats_combos_")][0]
        rows = combos.read_text(encoding="utf-8-sig").splitlines()
        self.assertEqual(rows[0].split(","),
                         ["generals", "win", "draw", "lose", "n", "winrate"])
        our = [r for r in rows if "가후" in r and "양기" in r][0]
        self.assertIn(",3,1,0,4,", our)      # AC-05: 집계와 동일 수치


class StatsHtmlTest(_Base):
    def test_report_sections_numbers_and_labels(self):
        html = render_report(self.stats)
        for anchor in ("id=\"overview\"", "id=\"decks\"", "id=\"records\"",
                       "id=\"combos\"", "id=\"picks\""):
            self.assertIn(anchor, html)
        self.assertIn("FIRST", html)                        # 아군 추정 표기
        self.assertIn(f"#{self.ids['u_b']}(상대B제안)", html)  # FR-06 미확정 표기
        self.assertIn("상대A", html)
        self.assertNotIn("http://", html)                   # 외부 리소스 0
        self.assertNotIn("https://", html)
        self.assertIn("제외", html)                         # NFR-03 제외 건수 표기

    def test_confirmed_label_after_relabel(self):
        """AC-06: 라벨 확정 후 재생성하면 확정 이름으로 표기된다."""
        rw = sqlite3.connect(self.db)
        rw.execute("UPDATE identities SET label='상대B', label_status='confirmed' "
                   "WHERE identity_id=?", (self.ids["u_b"],))
        rw.commit()
        rw.close()
        conn = sqlite3.connect(f"file:{self.db}?mode=ro", uri=True)
        html = render_report(collect(conn))
        conn.close()
        self.assertIn(">상대B<", html)
        self.assertNotIn(f"#{self.ids['u_b']}(", html)


class StatsCliTest(unittest.TestCase):
    def test_missing_or_empty_db_exits_1(self):
        from deckscan.cli import main
        with tempfile.TemporaryDirectory() as tmp:
            self.assertEqual(main(["stats", "--db", str(Path(tmp) / "none.db"),
                                   "--out", tmp]), 1)

    def test_generates_report_and_csvs(self):
        from deckscan.cli import main
        with tempfile.TemporaryDirectory() as tmp:
            db = str(Path(tmp) / "s.db")
            build_fixture(db)
            out = Path(tmp) / "stats"
            self.assertEqual(main(["stats", "--db", db, "--out", str(out)]), 0)
            self.assertEqual(len(list(out.glob("report_*.html"))), 1)
            self.assertEqual(len(list(out.glob("stats_*.csv"))), 4)


if __name__ == "__main__":
    unittest.main()
