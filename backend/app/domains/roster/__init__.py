"""
Roster domain (Milestone 8).

This package implements scheduling primitives needed for payroll-ready time
summaries:
- Shift templates per branch
- Branch default shift
- Effective-dated employee shift assignments
- Per-employee per-day overrides (shift change / force weekoff / force workday)

Payable summaries live in the attendance domain (attendance.payable_day_summaries)
to keep "worked time" + "expected time" adjacent.
"""

