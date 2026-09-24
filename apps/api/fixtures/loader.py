"""Seeds the graph and break population.

Reference rows are written the way ingestion writes them: a change closes the
existing edge and inserts a new one. Never updated in place.
"""

import json
import random
from datetime import date, timedelta
from pathlib import Path

from sqlalchemy import delete

from app.db.models_graph import BreakEmbedding, BreakEvent, Edge, Node

DATA = Path(__file__).parent / "data"
COB = date(2026, 8, 3)
ENTITY = "LE-APAC-01"

BOOKS = [f"PRIME-MB-{i:02d}" for i in range(1, 13)]

# The book that moved desk mid-period. Its old edge is closed, not updated,
# which is what makes as_of correctness testable.
MOVED_BOOK = "PRIME-MB-05"
MOVE_EFFECTIVE = date(2026, 7, 1)


async def load_all(session, *, commit: bool = True) -> None:
    """Load in explicit FK layers: nodes, then edges, then events.

    Each layer is flushed before the next. Edges and break events both carry
    FKs to node, and relying on the unit of work to order inserts across
    mappers that have no declared relationship() is not dependable.
    """
    await _clear(session)
    await _load_nodes(session)
    await session.flush()
    await _load_edges(session)
    await _load_breaks(session)
    await _load_priors(session)
    if commit:
        await session.commit()


async def _clear(session) -> None:
    for model in (BreakEmbedding, BreakEvent, Edge, Node):
        await session.execute(delete(model))


async def _load_nodes(session) -> None:
    for desk in ("APAC-CASH", "APAC-TREASURY"):
        session.add(
            Node(
                node_id=f"desk:{desk}",
                node_type="Desk",
                natural_key=desk,
                legal_entity_id=ENTITY,
                valid_from=date(2020, 1, 1),
            )
        )

    for book in BOOKS:
        session.add(
            Node(
                node_id=f"book:{book}",
                node_type="Book",
                natural_key=book,
                legal_entity_id=ENTITY,
                valid_from=date(2020, 1, 1),
            )
        )


async def _load_edges(session) -> None:
    for book in BOOKS:
        if book == MOVED_BOOK:
            session.add(
                Edge(
                    edge_id=f"e:{book}:old",
                    from_node_id=f"book:{book}",
                    to_node_id="desk:APAC-TREASURY",
                    edge_type="BELONGS_TO",
                    valid_from=date(2020, 1, 1),
                    valid_to=MOVE_EFFECTIVE - timedelta(days=1),
                )
            )
            session.add(
                Edge(
                    edge_id=f"e:{book}:new",
                    from_node_id=f"book:{book}",
                    to_node_id="desk:APAC-CASH",
                    edge_type="BELONGS_TO",
                    valid_from=MOVE_EFFECTIVE,
                    valid_to=None,
                )
            )
        else:
            session.add(
                Edge(
                    edge_id=f"e:{book}",
                    from_node_id=f"book:{book}",
                    to_node_id="desk:APAC-CASH",
                    edge_type="BELONGS_TO",
                    valid_from=date(2020, 1, 1),
                    valid_to=None,
                )
            )


def read_breaks() -> list[dict]:
    return json.loads((DATA / "breaks_small.json").read_text())


async def _load_breaks(session) -> None:
    for r in read_breaks():
        session.add(
            BreakEvent(
                break_id=r["break_id"],
                book_id=f"book:{r['book_ref']}",
                line_code=r["line_code"],
                cob_date=COB,
                fo_value=r["fo_value"],
                bo_value=r["bo_value"],
                delta=r["fo_value"] - r["bo_value"],
            )
        )


async def _load_priors(session) -> None:
    """42 prior P-204 resolutions at exactly 88% approval (37 of 42)."""
    rng = random.Random(204)
    approved_count = round(0.88 * 42)  # 37
    outcomes = ["approved"] * approved_count + ["rejected"] * (42 - approved_count)
    rng.shuffle(outcomes)
    for i, outcome in enumerate(outcomes):
        session.add(
            BreakEvent(
                break_id=f"prior-p204-{i:03d}",
                book_id=f"book:{BOOKS[i % len(BOOKS)]}",
                line_code="CASH",
                cob_date=date(2026, 6, 1),
                fo_value=100000.0,
                bo_value=99000.0,
                delta=1000.0,
                pattern_code="P-204",
                outcome=outcome,
                narrative="Nostro statement received after the 23:30 cutoff.",
            )
        )
