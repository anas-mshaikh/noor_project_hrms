"""Baseline squash (single revision).

Revision ID: 000000000000
Revises:
Create Date: 2026-02-17

This revision is a squashed baseline for local development. It replaces the
historical migration chain by creating the full schema as of the previous head,
plus required global seed rows (roles/permissions/request_types).

Important:
- This is intended for a single-developer workflow. Existing DB volumes should
  be reset (e.g. docker compose down -v) after squashing.
"""

from __future__ import annotations

from pathlib import Path

import sqlalchemy as sa
from alembic import op


# revision identifiers, used by Alembic.
revision = "000000000000"
down_revision = None
branch_labels = None
depends_on = None


def _split_sql(sql: str) -> list[str]:
    """
    Split a SQL script into individual statements.

    Handles:
    - single quotes
    - dollar-quoted strings ($$...$$ or $tag$...$tag$)
    - line comments (--)
    - block comments (/* ... */)

    We also skip psql meta-commands like "\\restrict" by filtering lines that
    start with a backslash.
    """

    # Drop psql meta-commands (pg_dump adds \\restrict at the top).
    cleaned_lines: list[str] = []
    for line in sql.splitlines():
        if line.startswith("\\"):
            continue
        cleaned_lines.append(line)
    s = "\n".join(cleaned_lines)

    stmts: list[str] = []
    buf: list[str] = []

    in_single = False
    in_double = False
    in_line_comment = False
    in_block_comment = False
    dollar_tag: str | None = None

    i = 0
    n = len(s)
    while i < n:
        ch = s[i]
        nxt = s[i + 1] if i + 1 < n else ""

        if in_line_comment:
            buf.append(ch)
            if ch == "\n":
                in_line_comment = False
            i += 1
            continue

        if in_block_comment:
            buf.append(ch)
            if ch == "*" and nxt == "/":
                buf.append(nxt)
                in_block_comment = False
                i += 2
            else:
                i += 1
            continue

        if dollar_tag is not None:
            # Inside a dollar-quoted string; only exit on exact tag match.
            if ch == "$":
                end = s.find(dollar_tag, i)
                if end == i:
                    buf.append(dollar_tag)
                    i += len(dollar_tag)
                    dollar_tag = None
                    continue
            buf.append(ch)
            i += 1
            continue

        if in_single:
            buf.append(ch)
            if ch == "'" and nxt == "'":
                # Escaped quote inside string.
                buf.append(nxt)
                i += 2
                continue
            if ch == "'":
                in_single = False
            i += 1
            continue

        if in_double:
            buf.append(ch)
            if ch == '"':
                in_double = False
            i += 1
            continue

        # Not in any quoted/comment context.
        if ch == "-" and nxt == "-":
            buf.append(ch)
            buf.append(nxt)
            in_line_comment = True
            i += 2
            continue

        if ch == "/" and nxt == "*":
            buf.append(ch)
            buf.append(nxt)
            in_block_comment = True
            i += 2
            continue

        if ch == "'":
            buf.append(ch)
            in_single = True
            i += 1
            continue

        if ch == '"':
            buf.append(ch)
            in_double = True
            i += 1
            continue

        if ch == "$":
            # Potential dollar tag start: $tag$ or $$.
            j = i + 1
            while j < n and (s[j].isalnum() or s[j] == "_"):
                j += 1
            if j < n and s[j] == "$":
                tag = s[i : j + 1]
                buf.append(tag)
                dollar_tag = tag
                i = j + 1
                continue
            buf.append(ch)
            i += 1
            continue

        if ch == ";":
            stmt = "".join(buf).strip()
            if stmt:
                stmts.append(stmt)
            buf = []
            i += 1
            continue

        buf.append(ch)
        i += 1

    tail = "".join(buf).strip()
    if tail:
        stmts.append(tail)
    return stmts


def upgrade() -> None:
    path = Path(__file__).with_name("000000000000_baseline.sql")
    sql = path.read_text(encoding="utf-8")
    conn = op.get_bind()
    for stmt in _split_sql(sql):
        # Use driver-level execution for DDL (fewer surprises than SQLAlchemy parsing).
        conn.exec_driver_sql(stmt)


def downgrade() -> None:
    # Not supported for a squashed baseline.
    raise RuntimeError("Downgrade is not supported for the squashed baseline revision")

