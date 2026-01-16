import unittest
import uuid
from datetime import datetime, timezone
from pathlib import Path
import sys

BACKEND_DIR = Path(__file__).resolve().parents[1]
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

from app.mobile.repository import MobileRow  # noqa: E402
from app.mobile.service import build_leaderboards, build_mobile_stats, rank_rows  # noqa: E402


class TestMobileRanking(unittest.TestCase):
    def test_rank_overall_with_tie_breakers(self) -> None:
        rows = [
            MobileRow(
                salesman_id="b",
                name="B",
                department="Grocery",
                qty=10,
                net_sales=100.0,
                bills=5,
                customers=20,
                return_customers=0,
                present=20,
                absent=0,
                work_minutes=1000,
                stocking_done=1,
                stocking_missed=0,
            ),
            MobileRow(
                salesman_id="a",
                name="A",
                department="Grocery",
                qty=10,
                net_sales=100.0,
                bills=6,  # higher bills should rank ahead
                customers=10,
                return_customers=0,
                present=20,
                absent=0,
                work_minutes=1000,
                stocking_done=1,
                stocking_missed=0,
            ),
        ]
        ranked = rank_rows(rows)
        rank_map = {r.salesman_id: r.rank_overall for r in ranked}
        self.assertEqual(rank_map["a"], 1)
        self.assertEqual(rank_map["b"], 2)

    def test_rank_department(self) -> None:
        rows = [
            MobileRow(
                salesman_id="a",
                name="A",
                department="Grocery",
                qty=10,
                net_sales=200.0,
                bills=5,
                customers=20,
                return_customers=0,
                present=20,
                absent=0,
                work_minutes=1000,
                stocking_done=1,
                stocking_missed=0,
            ),
            MobileRow(
                salesman_id="b",
                name="B",
                department="Grocery",
                qty=10,
                net_sales=100.0,
                bills=5,
                customers=20,
                return_customers=0,
                present=20,
                absent=0,
                work_minutes=1000,
                stocking_done=1,
                stocking_missed=0,
            ),
            MobileRow(
                salesman_id="c",
                name="C",
                department="Dairy",
                qty=10,
                net_sales=300.0,
                bills=5,
                customers=20,
                return_customers=0,
                present=20,
                absent=0,
                work_minutes=1000,
                stocking_done=1,
                stocking_missed=0,
            ),
        ]
        ranked = rank_rows(rows)
        dept_rank = {r.salesman_id: r.rank_department for r in ranked}
        self.assertEqual(dept_rank["a"], 1)
        self.assertEqual(dept_rank["b"], 2)
        self.assertEqual(dept_rank["c"], 1)

    def test_build_leaderboards(self) -> None:
        rows = [
            MobileRow(
                salesman_id="a",
                name="A",
                department="Grocery",
                qty=10,
                net_sales=200.0,
                bills=5,
                customers=20,
                return_customers=0,
                present=20,
                absent=0,
                work_minutes=1000,
                stocking_done=1,
                stocking_missed=0,
            ),
            MobileRow(
                salesman_id="b",
                name="B",
                department="Grocery",
                qty=10,
                net_sales=100.0,
                bills=5,
                customers=20,
                return_customers=0,
                present=20,
                absent=0,
                work_minutes=1000,
                stocking_done=1,
                stocking_missed=0,
            ),
        ]
        ranked = rank_rows(rows)
        overall, departments = build_leaderboards(ranked, month_key="2026-01", limit=10)
        self.assertEqual(overall.top[0].salesman_id, "a")
        self.assertIn("grocery", departments)
        self.assertEqual(departments["grocery"].top[0].salesman_id, "a")

    def test_build_mobile_stats(self) -> None:
        rows = [
            MobileRow(
                salesman_id="a",
                name="A",
                department=None,
                qty=None,
                net_sales=None,
                bills=None,
                customers=None,
                return_customers=None,
                present=None,
                absent=None,
                work_minutes=None,
                stocking_done=None,
                stocking_missed=None,
            )
        ]
        stats = build_mobile_stats(
            month_key="2026-01",
            dataset_id=uuid.uuid4(),
            store_id=uuid.uuid4(),
            org_id=uuid.uuid4(),
            rows=rows,
        )
        self.assertEqual(len(stats), 1)
        self.assertEqual(stats[0].rank_overall, 1)
        self.assertEqual(stats[0].rank_department, 1)


if __name__ == "__main__":
    unittest.main()
