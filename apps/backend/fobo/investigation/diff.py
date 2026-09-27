"""What changed between two workflow versions, and re-applying a stale draft.

Pure functions over full configs as dump_config produces them. The Workflow
tab shows `diff` against the active version; `rebase` rebuilds a draft whose
base is no longer active, so a controller never approves a draft that would
silently undo someone else's change.
"""

import copy
from dataclasses import asdict, dataclass

SCALARS = ("name", "version")
LISTS = ("steps", "pause_before")


@dataclass(frozen=True)
class Change:
    path: str
    kind: str  # added | removed | moved | changed
    before: object = None
    after: object = None

    def as_dict(self) -> dict:
        return asdict(self)


def _lcs(a: list, b: list) -> set:
    """Items on the longest common subsequence: the ones that did not move."""
    n, m = len(a), len(b)
    dp = [[0] * (m + 1) for _ in range(n + 1)]
    for i in range(n - 1, -1, -1):
        for j in range(m - 1, -1, -1):
            dp[i][j] = dp[i + 1][j + 1] + 1 if a[i] == b[j] else max(dp[i + 1][j], dp[i][j + 1])
    keep, i, j = set(), 0, 0
    while i < n and j < m:
        if a[i] == b[j]:
            keep.add(a[i])
            i, j = i + 1, j + 1
        elif dp[i + 1][j] >= dp[i][j + 1]:
            i += 1
        else:
            j += 1
    return keep


def _step_changes(before: list, after: list) -> list[Change]:
    out = [Change(f"steps.{s}", "removed", before=before.index(s)) for s in before if s not in after]
    out += [Change(f"steps.{s}", "added", after=after.index(s)) for s in after if s not in before]
    kept_before = [s for s in before if s in after]
    kept_after = [s for s in after if s in before]
    stayed = _lcs(kept_before, kept_after)
    out += [
        Change(f"steps.{s}", "moved", before=before.index(s), after=after.index(s))
        for s in kept_after if s not in stayed
    ]
    return out


def _pause_changes(before: list, after: list) -> list[Change]:
    return (
        [Change(f"pause_before.{s}", "removed") for s in before if s not in after]
        + [Change(f"pause_before.{s}", "added") for s in after if s not in before]
    )


def _leaves(settings: dict) -> dict[str, object]:
    return {
        f"settings.{section}.{key}": value
        for section, fields in settings.items()
        for key, value in fields.items()
    }


def diff(base: dict, other: dict) -> list[Change]:
    out = [
        Change(k, "changed", before=base.get(k), after=other.get(k))
        for k in SCALARS if base.get(k) != other.get(k)
    ]
    out += _step_changes(base["steps"], other["steps"])
    out += _pause_changes(base["pause_before"], other["pause_before"])
    b, o = _leaves(base["settings"]), _leaves(other["settings"])
    out += [
        Change(path, "changed", before=b.get(path), after=o.get(path))
        for path in list(b) + [p for p in o if p not in b]
        if b.get(path) != o.get(path)
    ]
    return out


def _pick(base, draft, active) -> tuple[object, bool]:
    """The draft's value where the draft changed it, else the active one's.
    A conflict is both sides changing the same item differently."""
    if draft == base:
        return active, False
    return draft, active != base and active != draft


def rebase(base: dict, draft: dict, active: dict) -> tuple[dict, list[str]]:
    merged = copy.deepcopy(active)
    conflicts: list[str] = []
    for key in SCALARS + LISTS:
        value, clash = _pick(base.get(key), draft.get(key), active.get(key))
        merged[key] = copy.deepcopy(value)
        if clash:
            conflicts.append(key)
    b, d, a = _leaves(base["settings"]), _leaves(draft["settings"]), _leaves(active["settings"])
    settings: dict[str, dict] = {}
    for path in list(a) + [p for p in d if p not in a]:
        value, clash = _pick(b.get(path), d.get(path), a.get(path))
        _, section, name = path.split(".", 2)
        settings.setdefault(section, {})[name] = copy.deepcopy(value)
        if clash:
            conflicts.append(path)
    merged["settings"] = settings
    return merged, conflicts
