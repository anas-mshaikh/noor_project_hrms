import sys
import unittest
from datetime import time, timedelta
from decimal import Decimal
from pathlib import Path

# Ensure `import app.*` works when tests are run from repo root.
BACKEND_DIR = Path(__file__).resolve().parents[1]
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

from app.imports.parsing import (  # noqa: E402
    parse_attendance_sheet,
    parse_decimal,
    parse_pos_sheet,
    parse_ratio,
    parse_work_minutes,
)


class TestImportParsing(unittest.TestCase):
    def test_parse_decimal_commas(self) -> None:
        self.assertEqual(parse_decimal("1,234.50"), Decimal("1234.50"))

    def test_parse_decimal_parentheses_negative(self) -> None:
        self.assertEqual(parse_decimal("(1,234)"), Decimal("-1234"))

    def test_parse_work_minutes_hhmm(self) -> None:
        self.assertEqual(parse_work_minutes("02:30"), 150)

    def test_parse_work_minutes_time(self) -> None:
        self.assertEqual(parse_work_minutes(time(1, 15)), 75)

    def test_parse_work_minutes_timedelta(self) -> None:
        self.assertEqual(parse_work_minutes(timedelta(hours=2, minutes=5)), 125)

    def test_parse_work_minutes_excel_fraction(self) -> None:
        # 0.5 day = 12 hours = 720 minutes
        self.assertEqual(parse_work_minutes(0.5), 720)

    def test_parse_ratio(self) -> None:
        self.assertEqual(parse_ratio("10/1"), (10, 1))

    def test_pos_sheet_header_detection_and_total_stop(self) -> None:
        rows = [
            ["Some Store Report", None, None],
            [None, None, None],
            ["POS Summary", None, None],
            ["Salesman", "Qty", "Net Sales", "Customers"],
            ["Rahul", "10", "1,200.50", "12"],
            ["TOTAL", "10", "1,200.50", "12"],
            ["Should not parse", "1", "1", "1"],
        ]
        out = parse_pos_sheet("POS", rows)
        self.assertEqual(len(out.pos), 1)
        sid = next(iter(out.pos.keys()))
        self.assertIn(sid, out.employees)
        self.assertEqual(out.employees[sid].name, "Rahul")
        self.assertEqual(out.pos[sid].qty, Decimal("10"))

    def test_pos_sheet_header_detection_no_of_customers(self) -> None:
        # Real-world reports often use "No. of Customers" instead of "Customers".
        rows = [
            ["Salesman Wise From Dated 01-01-2026 To Dated 31-01-2026", None],
            ["Company: Sakarwala", None],
            [None, None],
            ["Salesman", "Qty", "Net Sales", "No. of Bills", "No. of Customers"],
            ["Rahul", "10", "1,200.50", "3", "12"],
            ["TOTAL", "10", "1,200.50", "3", "12"],
        ]
        out = parse_pos_sheet("POS", rows)
        self.assertEqual(len(out.pos), 1)
        sid = next(iter(out.pos.keys()))
        self.assertEqual(out.employees[sid].name, "Rahul")
        self.assertEqual(out.pos[sid].customers, 12)

    def test_attendance_sheet_blank_row_stop(self) -> None:
        rows = [
            ["Attendance", None],
            ["Salesman", "Present", "Absent", "Work Hours", "Stocking"],
            ["Rahul", "1", "0", "08:30", "10/1"],
            [None, None, None, None, None],  # stop here
            ["Someone Else", "1", "0", "08:00", "1/0"],  # should not be parsed
        ]
        out = parse_attendance_sheet("Attendance", rows)
        self.assertEqual(len(out.attendance), 1)
        sid = next(iter(out.attendance.keys()))
        self.assertEqual(out.attendance[sid].work_minutes, 510)


if __name__ == "__main__":
    unittest.main()
