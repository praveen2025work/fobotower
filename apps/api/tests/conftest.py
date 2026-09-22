"""Test isolation.

Every test starts from empty tables. Without this the suite is not
re-runnable: primary keys collide on the second run.
"""

import pytest
from sqlalchemy import text

from app.db.base import get_session

# Child tables first.
TABLES = [
    "controller_decision",
    "pattern_group",
    "evidence_item",
    "analysis_version",
    "investigation_session",
    "break_embedding",
    "break_event",
    "edge",
    "node",
]


@pytest.fixture(autouse=True)
async def clean_tables():
    async with get_session() as s:
        await s.execute(text(f"TRUNCATE {', '.join(TABLES)} CASCADE"))
        await s.commit()
    yield
