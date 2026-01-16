import unittest
from collections import namedtuple
from pathlib import Path
import sys

BACKEND_DIR = Path(__file__).resolve().parents[1]
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

from app.mobile.repository import rows_to_mobile  # noqa: E402


class TestMobileRepository(unittest.TestCase):
    def test_rows_to_mobile(self) -> None:
        Row = namedtuple(
            "Row",
            [
                "salesman_id",
                "name",
                "department",
                "qty",
                "net_sales",
                "bills",
                "customers",
                "return_customers",
                "present",
                "absent",
                "work_minutes",
                "stocking_done",
                "stocking_missed",
            ],
        )
        rows = [
            Row(
                salesman_id="a",
                name="Aamir",
                department="Bakery",
                qty=10,
                net_sales=100.5,
                bills=3,
                customers=8,
                return_customers=2,
                present=20,
                absent=2,
                work_minutes=600,
                stocking_done=5,
                stocking_missed=1,
            )
        ]
        out = rows_to_mobile(rows)
        self.assertEqual(len(out), 1)
        self.assertEqual(out[0].salesman_id, "a")
        self.assertEqual(out[0].net_sales, 100.5)


if __name__ == "__main__":
    unittest.main()
