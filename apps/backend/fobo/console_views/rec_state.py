"""How a run's status reads on the Helix console.

The pipeline is ingest -> ready -> analysis -> signoff -> posting. A run's
status says which step it has reached; the steps array is derived from it,
never stored, so the two cannot disagree.
"""

STATUS = {
    "scheduled": "Awaiting Ready",
    "in_progress": "In Progress",
    "blocked": "Blocked",
    "awaiting": "Awaiting Sign-off",
    "cleared": "Cleared",
}

STEPS = {
    "scheduled": ["active", "pending", "pending", "pending", "pending"],
    "in_progress": ["done", "done", "active", "pending", "pending"],
    "blocked": ["done", "done", "blocked", "pending", "pending"],
    "awaiting": ["done", "done", "done", "active", "pending"],
    "cleared": ["done", "done", "done", "done", "done"],
}

# break_event.outcome -> the adjustment status a controller sees.
ADJ_STATUS = {
    None: "Pending",
    "approved": "Approved",
    "rejected": "Rejected",
    "posted": "Posted",
}


def helix_status(run_status: str) -> str:
    return STATUS[run_status]


def steps(run_status: str) -> list[str]:
    return list(STEPS[run_status])
