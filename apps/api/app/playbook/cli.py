"""Playbook command line.

    python -m app.playbook.cli validate   check the YAML without touching the database
    python -m app.playbook.cli load       validate, then load it into the graph
    python -m app.playbook.cli show       print what is currently loaded

Run from apps/api. Point FOBO_PLAYBOOK_PATH at a different file to try an
edit without changing the checked-in one.
"""

import asyncio
import re
import sys

from pydantic import ValidationError

from app.playbook.loader import load_playbook, loaded_version, playbook_path, read_playbook


def _validate() -> int:
    path = playbook_path()
    try:
        pb = read_playbook(path)
    except (ValidationError, ValueError) as exc:
        print(f"INVALID  {path}")
        for line in str(exc).splitlines():
            line = re.sub(r"\s*\[type=.*$", "", line).strip()
            if line.startswith("- "):
                print(f"  {line}")
        return 1
    unset = [k for k, v in pb.policy.items() if v.value is None]
    deterministic = [c for c, d in pb.categories.items() if d.determinism == "deterministic"]
    print(f"VALID    {path}")
    print(f"  version {pb.version}, effective from {pb.effective_from}")
    print(f"  {len(pb.tests)} tests, {len(pb.findings)} findings, "
          f"{len(pb.categories)} categories ({len(deterministic)} deterministic)")
    print(f"  policy: {len(pb.policy) - len(unset)} set, {len(unset)} unset"
          + (f" -> {', '.join(unset)}" if unset else ""))
    if unset:
        print("  (Rule P1: a POST depending on an unset parameter needs controller confirmation)")
    return 0


async def _load() -> int:
    if _validate() != 0:
        return 1
    from app.db.base import get_session

    async with get_session() as s:
        pb = await load_playbook(s)
    print(f"LOADED   version {pb.version} into the knowledge graph")
    return 0


async def _show() -> int:
    from app.db.base import get_session
    from app.graph.ontology import OntologyRepository

    async with get_session() as s:
        version = await loaded_version(s)
        if version is None:
            print("No playbook loaded. Run:  python -m app.playbook.cli load")
            return 1
        pb = read_playbook()
        repo = OntologyRepository(s)
        print(f"Loaded playbook version {version}\n")
        for tid in pb.tests:
            nxt = await repo.required_on_fail(tid, pb.effective_from)
            ev = await repo.evidence_required(tid, pb.effective_from)
            extra = []
            if nxt:
                extra.append(f"on fail -> {', '.join(nxt)}")
            if ev:
                extra.append(f"needs {', '.join(ev)}")
            print(f"  {tid:5} {pb.tests[tid].checks[:52]:52} {'; '.join(extra)}")
    return 0


def main() -> int:
    cmd = sys.argv[1] if len(sys.argv) > 1 else "validate"
    if cmd == "validate":
        return _validate()
    if cmd == "load":
        return asyncio.run(_load())
    if cmd == "show":
        return asyncio.run(_show())
    print(__doc__)
    return 2


if __name__ == "__main__":
    sys.exit(main())
