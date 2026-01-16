from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field


class MonthlyEmployeeStatsV1(BaseModel):
    """
    Mobile Data Contract v1: one employee's monthly stats + ranks.

    This is the canonical Firestore document payload for the mobile app.
    """

    month_key: str
    published_dataset_id: str
    store_id: str
    org_id: str

    salesman_id: str
    name: str
    department: str | None = None

    qty: float | None = None
    net_sales: float | None = None
    bills: int | None = None
    customers: int | None = None
    return_customers: int | None = None

    present: int | None = None
    absent: int | None = None
    work_minutes: int | None = None
    stocking_done: int | None = None
    stocking_missed: int | None = None

    rank_overall: int
    rank_department: int

    dataset_id: str
    synced_at: datetime


class LeaderboardEntryV1(BaseModel):
    rank: int
    salesman_id: str
    name: str
    department: str | None = None
    metric_value: float


class LeaderboardDocV1(BaseModel):
    """
    Firestore leaderboard document payload.
    """

    month_key: str
    metric: Literal["net_sales"] = Field(default="net_sales")
    updated_at: datetime
    top: list[LeaderboardEntryV1]


class MobileSyncPreviewOut(BaseModel):
    month_key: str
    store_id: str
    org_id: str
    published_dataset_id: str
    employees: list[MonthlyEmployeeStatsV1]


class MobileLeaderboardPreviewOut(BaseModel):
    month_key: str
    store_id: str
    org_id: str
    published_dataset_id: str
    overall: LeaderboardDocV1
    departments: dict[str, LeaderboardDocV1]
