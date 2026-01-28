import unittest
from pathlib import Path
import sys
import uuid

BACKEND_DIR = Path(__file__).resolve().parents[1]
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

from app.models.models import EmployeeSkill, TaskRequiredSkill  # noqa: E402
from app.work.service import CandidateScore, AutoTaskAssigner  # noqa: E402


class TestWorkAutoAssignment(unittest.TestCase):
    def test_meets_required_skills_true(self) -> None:
        employee_id = uuid.uuid4()
        s1 = uuid.uuid4()
        s2 = uuid.uuid4()

        reqs = [
            TaskRequiredSkill(
                task_id=uuid.uuid4(),
                skill_id=s1,
                min_proficiency=3,
                required=True,
            ),
            TaskRequiredSkill(
                task_id=uuid.uuid4(),
                skill_id=s2,
                min_proficiency=1,
                required=False,  # optional should not block eligibility
            ),
        ]
        emp_skills = {
            s1: EmployeeSkill(
                employee_id=employee_id,
                skill_id=s1,
                proficiency=3,
                confidence=1.0,
            )
        }

        self.assertTrue(AutoTaskAssigner._meets_required_skills(emp_skills, reqs))

    def test_meets_required_skills_false_missing(self) -> None:
        employee_id = uuid.uuid4()
        s1 = uuid.uuid4()

        reqs = [
            TaskRequiredSkill(
                task_id=uuid.uuid4(),
                skill_id=s1,
                min_proficiency=2,
                required=True,
            )
        ]
        emp_skills: dict[uuid.UUID, EmployeeSkill] = {}

        self.assertFalse(AutoTaskAssigner._meets_required_skills(emp_skills, reqs))

    def test_base_skill_score_includes_optional_if_met(self) -> None:
        employee_id = uuid.uuid4()
        s_required = uuid.uuid4()
        s_optional = uuid.uuid4()

        reqs = [
            TaskRequiredSkill(
                task_id=uuid.uuid4(),
                skill_id=s_required,
                min_proficiency=2,
                required=True,
            ),
            TaskRequiredSkill(
                task_id=uuid.uuid4(),
                skill_id=s_optional,
                min_proficiency=1,
                required=False,
            ),
        ]

        emp_skills = {
            s_required: EmployeeSkill(
                employee_id=employee_id,
                skill_id=s_required,
                proficiency=3,
                confidence=1.0,
            ),
            s_optional: EmployeeSkill(
                employee_id=employee_id,
                skill_id=s_optional,
                proficiency=2,
                confidence=0.5,
            ),
        }

        score = AutoTaskAssigner._base_skill_score(emp_skills, reqs)
        # required: 3 * 1.0 = 3.0
        # optional: 2 * 0.5 = 1.0
        self.assertAlmostEqual(score, 4.0, places=6)

    def test_pick_best_candidate_tie_break(self) -> None:
        a = CandidateScore(
            employee_id=uuid.uuid4(),
            employee_code="b",
            employee_name="B",
            score=10.0,
            base_skill_score=10.0,
            active_assignment_count=1,
            is_present=True,
        )
        b = CandidateScore(
            employee_id=uuid.uuid4(),
            employee_code="a",
            employee_name="A",
            score=10.0,
            base_skill_score=10.0,
            active_assignment_count=0,  # fewer active assignments should win
            is_present=True,
        )
        best = AutoTaskAssigner._pick_best_candidate([a, b])
        self.assertIsNotNone(best)
        self.assertEqual(best.employee_code, "a")


if __name__ == "__main__":
    unittest.main()

