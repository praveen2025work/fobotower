"""Rank candidate causes.

Fast path: a single positive candidate is assigned 10000 bps deterministically
and the model is skipped. Roughly 60% of breaks take this path, which is the
point of it — it saves cost, latency and variance on cases that need no
judgement at all.

Multi-candidate ranking calls the reasoning client with forced tool use in
Phase 3. Until then those breaks are marked and carried.
"""

from app.workflow.state import InvestigationState

FULL_SHARE_BPS = 10000
NEEDS_MODEL = "needs_model"


async def rank(state: InvestigationState, *, session) -> dict:
    ranking: dict = {}
    model_skipped = True

    for brk in state["breaks"]:
        bid = brk["break_id"]
        positives = [c for c in state["candidates"][bid] if c.positive]
        if len(positives) == 1:
            ranking[bid] = [
                {
                    "candidate_id": positives[0].check_id,
                    "share_bps": FULL_SHARE_BPS,
                    "evidence_ids": positives[0].supporting_ids,
                }
            ]
        else:
            ranking[bid] = NEEDS_MODEL
            model_skipped = False

    return {"ranking": ranking, "model_skipped": model_skipped}
