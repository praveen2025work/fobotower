"""Every step the workflow can run, and what each one needs and produces.

The step code lives in app/workflow/nodes/. This registry is what lets the
order be configured safely: the validator checks each step's inputs are
produced by an earlier step, so a reordering that cannot work is rejected
before a run starts rather than failing half way through with a KeyError.

Adding a step: write the node, register it here with honest `needs` and
`produces`, then list it in config/workflow/fobo-investigation.yaml.
"""

from dataclasses import dataclass, field

from app.workflow.nodes.draft import draft
from app.workflow.nodes.gather import gather
from app.workflow.nodes.group import group
from app.workflow.nodes.rank import rank
from app.workflow.nodes.reason import reason
from app.workflow.nodes.record import record
from app.workflow.nodes.resolve import resolve
from app.workflow.nodes.validate import validate
from app.workflow.state import InvestigationState


async def review(state: InvestigationState) -> dict:
    """Pure pass-through. The pause happens before this step runs."""
    return {"review_cycles": state.get("review_cycles", 0) + 1}


@dataclass(frozen=True)
class Step:
    name: str
    fn: object
    label: str
    description: str
    needs: frozenset[str]
    produces: frozenset[str]
    # Takes the database session (bound at build time).
    uses_session: bool = True
    # Can end the run early with outcome=escalated.
    can_escalate: bool = False
    # Cannot be removed from the workflow, and why.
    required_because: str | None = None
    # Must come after these steps even when no data dependency says so.
    must_follow: frozenset[str] = field(default_factory=frozenset)
    # Who or what decides the step's output; the Workflow tab tags each step
    # with it. One of DECIDED_BY.
    decided_by: str = "code"


# Supplied by whoever starts the run (see api/routes/recs.py _initial_state).
INITIAL_INPUTS = frozenset({
    "investigation_session_id", "reconciliation_id", "master_book",
    "business_date", "run_id", "caller", "breaks", "book_resolutions",
    "evidence_gaps", "hypothesis_attempts", "review_cycles", "workflow_version",
})

# Written into the state by the controller's decision on resume, not by a node.
RESUME_INPUTS = frozenset({"decisions"})


def _s(*names: str) -> frozenset[str]:
    return frozenset(names)


STEPS: dict[str, Step] = {s.name: s for s in [
    Step("resolve", resolve, "Resolve books", "Pin each break's book to the business date",
         needs=_s("breaks", "business_date", "caller"),
         produces=_s("book_resolutions", "as_of"),
         can_escalate=True,
         required_because="every later step works on resolved books"),
    Step("gather", gather, "Gather evidence", "Deltas, cause checks, lineage and priors",
         needs=_s("as_of", "book_resolutions", "breaks", "caller", "evidence_gaps",
                  "investigation_session_id", "master_book", "reconciliation_id"),
         produces=_s("deltas", "candidates", "priors", "lineage", "evidence_gaps"),
         can_escalate=True,
         required_because="there is nothing to explain without the deltas and checks"),
    Step("group", group, "Group patterns", "Collapse breaks into pattern groups",
         needs=_s("breaks", "candidates", "investigation_session_id", "priors", "run_id"),
         produces=_s("pattern_groups", "reasons", "group_meta", "ungrounded_breaks"),
         required_because="the playbook step and the draft both need the pattern groups"),
    Step("reason", reason, "Apply playbook", "Settle by rule; route the rest to the reasoner",
         needs=_s("breaks", "business_date", "candidates", "deltas", "evidence_gaps",
                  "lineage", "priors", "reasons"),
         produces=_s("findings", "determinism", "reasoning_error", "evidence_gaps"),
         required_because="it applies the playbook and the hard verdict guards (R2, R6, P1)",
         decided_by="playbook+reasoner"),
    Step("rank", rank, "Rank causes", "Order candidate causes per break",
         needs=_s("breaks", "candidates"),
         produces=_s("ranking", "model_skipped"),
         decided_by="code+model"),
    Step("draft", draft, "Draft analysis", "Write the four-part narrative",
         needs=_s("breaks", "deltas", "evidence_gaps", "pattern_groups"),
         produces=_s("draft"),
         required_because="the controller reviews it and record writes it",
         decided_by="template"),
    Step("validate", validate, "Validate", "Check every figure traces to a delta",
         needs=_s("breaks", "deltas", "draft", "evidence_gaps", "hypothesis_attempts",
                  "investigation_session_id", "pattern_groups", "reconciliation_id"),
         produces=_s("validation_errors"),
         required_because="no ungrounded figure may reach a controller"),
    Step("review", review, "Human sign-off", "Controller approves or rejects",
         needs=_s("pattern_groups", "findings"),
         produces=_s("review_cycles"),
         uses_session=False,
         required_because="no decision is recorded without a person",
         must_follow=_s("reason", "validate"),
         decided_by="human"),
    Step("record", record, "Record outcome", "Write decisions; they become tomorrow's priors",
         needs=_s("business_date", "decisions", "draft", "investigation_session_id",
                  "master_book", "pattern_groups", "reconciliation_id", "run_id"),
         produces=_s("outcome"),
         required_because="an investigation that is never recorded never happened",
         must_follow=_s("review")),
]}

REQUIRED_STEPS = frozenset(n for n, s in STEPS.items() if s.required_because)
PAUSE_REQUIRED = frozenset({"review"})

DECIDED_BY = ("code", "playbook+reasoner", "code+model", "template", "human")


def catalogue() -> list[dict]:
    """Every registered step as the Workflow tab shows it, in registry order."""
    return [
        {
            "name": s.name,
            "label": s.label,
            "description": s.description,
            "decided_by": s.decided_by,
            "removable": s.required_because is None,
            "required_because": s.required_because,
            "can_escalate": s.can_escalate,
            "needs": sorted(s.needs),
            "produces": sorted(s.produces),
            "must_follow": sorted(s.must_follow),
        }
        for s in STEPS.values()
    ]
