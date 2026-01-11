import sys
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path
from uuid import UUID

# Ensure `import app.*` works when tests are run from repo root.
BACKEND_DIR = Path(__file__).resolve().parents[1]
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

from app.worker.reliability import (  # noqa: E402
    DoorEventStrength,
    PendingDoorEvent,
    Tracklet,
    classify_event_strength,
    exit_grace_expired,
    find_unique_stitch_candidate,
    group_stitched_tracklets,
    is_track_stable,
    should_cancel_exit_pending,
    should_commit_event,
    should_drop_pending_entry_on_end,
)


class TestReliabilityHelpers(unittest.TestCase):
    def test_classify_event_strength_defaults_to_weak(self) -> None:
        self.assertEqual(classify_event_strength(None), DoorEventStrength.WEAK)
        self.assertEqual(classify_event_strength("unknown_reason"), DoorEventStrength.WEAK)

    def test_classify_event_strength_strong(self) -> None:
        self.assertEqual(classify_event_strength("line_crossing"), DoorEventStrength.STRONG)
        self.assertEqual(
            classify_event_strength("line_crossing_first_stable_inside"),
            DoorEventStrength.STRONG,
        )

    def test_classify_event_strength_medium(self) -> None:
        self.assertEqual(classify_event_strength("zone_transition_no_line"), DoorEventStrength.MEDIUM)

    def test_is_track_stable_by_hits(self) -> None:
        now = datetime.now(timezone.utc)
        self.assertTrue(
            is_track_stable(
                first_ts=None,
                now_ts=now,
                hits=3,
                min_age_sec=10.0,
                min_hits=3,
            )
        )

    def test_is_track_stable_by_age(self) -> None:
        t0 = datetime.now(timezone.utc)
        now = t0 + timedelta(seconds=1.0)
        self.assertTrue(
            is_track_stable(
                first_ts=t0,
                now_ts=now,
                hits=1,
                min_age_sec=0.6,
                min_hits=3,
            )
        )

    def test_should_commit_event(self) -> None:
        self.assertTrue(should_commit_event(strength=DoorEventStrength.STRONG, stable=False))
        self.assertFalse(should_commit_event(strength=DoorEventStrength.WEAK, stable=False))
        self.assertTrue(should_commit_event(strength=DoorEventStrength.WEAK, stable=True))

    def test_should_drop_pending_entry_on_end(self) -> None:
        now = datetime.now(timezone.utc)
        e = PendingDoorEvent(
            event_type="entry",
            ts=now,
            is_inferred=True,
            confidence=0.3,
            strength=DoorEventStrength.WEAK,
            snapshot_path="x.jpg",
            meta={"reason": "first_seen_inside"},
        )
        self.assertTrue(should_drop_pending_entry_on_end(e))

        x = PendingDoorEvent(
            event_type="exit",
            ts=now,
            is_inferred=True,
            confidence=0.3,
            strength=DoorEventStrength.WEAK,
            snapshot_path=None,
            meta={"reason": "track_ended_inside"},
        )
        self.assertFalse(should_drop_pending_entry_on_end(x))

        strong_entry = PendingDoorEvent(
            event_type="entry",
            ts=now,
            is_inferred=False,
            confidence=0.9,
            strength=DoorEventStrength.STRONG,
            snapshot_path="x.jpg",
            meta={"reason": "line_crossing"},
        )
        self.assertFalse(should_drop_pending_entry_on_end(strong_entry))

    def test_exit_grace_expired(self) -> None:
        t0 = datetime.now(timezone.utc)
        self.assertFalse(exit_grace_expired(started_ts=t0, now_ts=t0 + timedelta(seconds=2), grace_sec=30))
        self.assertTrue(exit_grace_expired(started_ts=t0, now_ts=t0 + timedelta(seconds=31), grace_sec=30))

    def test_should_cancel_exit_pending(self) -> None:
        emp = UUID("aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa")
        t0 = datetime.now(timezone.utc)

        # Matches employee, within grace, high confidence, in door ROI => cancel.
        self.assertTrue(
            should_cancel_exit_pending(
                pending_employee_id=emp,
                started_ts=t0,
                now_ts=t0 + timedelta(seconds=5),
                grace_sec=30,
                new_employee_id=emp,
                new_lock_confidence=0.9,
                min_lock_score=0.75,
                new_in_door_roi=True,
            )
        )

        # Not in door ROI => do not cancel.
        self.assertFalse(
            should_cancel_exit_pending(
                pending_employee_id=emp,
                started_ts=t0,
                now_ts=t0 + timedelta(seconds=5),
                grace_sec=30,
                new_employee_id=emp,
                new_lock_confidence=0.9,
                min_lock_score=0.75,
                new_in_door_roi=False,
            )
        )

        # Low confidence => do not cancel.
        self.assertFalse(
            should_cancel_exit_pending(
                pending_employee_id=emp,
                started_ts=t0,
                now_ts=t0 + timedelta(seconds=5),
                grace_sec=30,
                new_employee_id=emp,
                new_lock_confidence=0.6,
                min_lock_score=0.75,
                new_in_door_roi=True,
            )
        )

        # Different employee => do not cancel.
        self.assertFalse(
            should_cancel_exit_pending(
                pending_employee_id=emp,
                started_ts=t0,
                now_ts=t0 + timedelta(seconds=5),
                grace_sec=30,
                new_employee_id=UUID("bbbbbbbb-bbbb-bbbb-bbbb-bbbbbbbbbbbb"),
                new_lock_confidence=0.9,
                min_lock_score=0.75,
                new_in_door_roi=True,
            )
        )

    def test_find_unique_stitch_candidate_requires_inside_continuity(self) -> None:
        emp = UUID("aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa")
        t0 = datetime.now(timezone.utc)

        a = Tracklet(
            track_key="t1",
            employee_id=emp,
            lock_confidence=0.9,
            start_ts=t0,
            end_ts=t0 + timedelta(seconds=10),
            first_zone="inside",
            last_zone="outside",  # not inside => should not stitch
        )
        b = Tracklet(
            track_key="t2",
            employee_id=emp,
            lock_confidence=0.9,
            start_ts=t0 + timedelta(seconds=12),
            end_ts=t0 + timedelta(seconds=20),
            first_zone="inside",
            last_zone="inside",
        )

        idx = find_unique_stitch_candidate(
            tracklets=[a, b],
            idx=1,
            gap_sec=8,
            min_lock_score=0.75,
            require_unique_candidate=True,
            require_inside_continuity=True,
        )
        self.assertIsNone(idx)

    def test_group_stitched_tracklets_happy_path(self) -> None:
        emp = UUID("aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa")
        t0 = datetime.now(timezone.utc)

        a = Tracklet(
            track_key="t1",
            employee_id=emp,
            lock_confidence=0.9,
            start_ts=t0,
            end_ts=t0 + timedelta(seconds=10),
            first_zone="inside",
            last_zone="inside",
        )
        b = Tracklet(
            track_key="t2",
            employee_id=emp,
            lock_confidence=0.9,
            start_ts=t0 + timedelta(seconds=12),
            end_ts=t0 + timedelta(seconds=20),
            first_zone="inside",
            last_zone="inside",
        )

        mapping = group_stitched_tracklets(
            tracklets=[a, b],
            gap_sec=8,
            min_lock_score=0.75,
            require_unique_candidate=True,
            require_inside_continuity=True,
        )
        self.assertEqual(mapping["t1"], mapping["t2"])  # stitched into same session

    def test_group_stitched_tracklets_ambiguity_blocks(self) -> None:
        emp = UUID("aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa")
        t0 = datetime.now(timezone.utc)

        # Two possible previous candidates within the gap window => no stitch when unique required.
        a1 = Tracklet(
            track_key="t1",
            employee_id=emp,
            lock_confidence=0.9,
            start_ts=t0,
            end_ts=t0 + timedelta(seconds=10),
            first_zone="inside",
            last_zone="inside",
        )
        a2 = Tracklet(
            track_key="t2",
            employee_id=emp,
            lock_confidence=0.9,
            start_ts=t0 + timedelta(seconds=1),
            end_ts=t0 + timedelta(seconds=11),
            first_zone="inside",
            last_zone="inside",
        )
        b = Tracklet(
            track_key="t3",
            employee_id=emp,
            lock_confidence=0.9,
            start_ts=t0 + timedelta(seconds=15),
            end_ts=t0 + timedelta(seconds=25),
            first_zone="inside",
            last_zone="inside",
        )

        mapping = group_stitched_tracklets(
            tracklets=[a1, a2, b],
            gap_sec=8,
            min_lock_score=0.75,
            require_unique_candidate=True,
            require_inside_continuity=True,
        )
        # Should not stitch because b has two previous candidates in the window.
        self.assertEqual(mapping["t3"], "t3")


if __name__ == "__main__":
    unittest.main()

