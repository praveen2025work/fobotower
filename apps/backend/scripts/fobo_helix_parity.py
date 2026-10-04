"""FOBO → Helix parity check: does Helix reach the same answer as the old FOBO run?

Run the same book and COB through the old FOBO agent and through Helix, then
compare, break by break, the three things the playbook decides: category,
side and verdict. Use it during the migration's parallel run; the cut-over
needs a clean result on every book for an agreed number of COBs.

    cd apps/backend
    # Helix side: a case JSON saved from the API, or fetched here
    curl -s -H 'X-Helix-User: frank' localhost:8300/api/cases/<case_id> > helix.json
    .venv/bin/python scripts/fobo_helix_parity.py --helix helix.json --old old_run.csv

    .venv/bin/python scripts/fobo_helix_parity.py --old old_run.json \\
        --api http://localhost:8300 --case-id <case_id> --user frank

The old run is a CSV or JSON list with one row per break. Its column names
default to instrument, category, side and verdict; rename them with
--old-columns "id=break_ref,category=cat,side=origin,verdict=recommendation".

Exit status: 0 when every break agrees, 1 when any differs or is missing on
one side, 2 on bad input.
"""

import argparse
import csv
import json
import sys
import urllib.request
from pathlib import Path

FIELDS = ("category", "side", "verdict")


def _norm(value) -> str:
    return "" if value is None else str(value).strip().upper()


def helix_rows(case: dict) -> dict[str, dict]:
    """Per break (keyed by the case's id field): category, side and verdict.

    Category and side are on each item (the classify step); the verdict is on
    the finding of the group the item belongs to. A break no group holds is out
    of scope (e.g. under materiality) and has no verdict.
    """
    id_field = case.get("id_field") or "item_id"
    verdict_of = {}
    for g in case.get("groups", []):
        verdict = (g.get("finding") or {}).get("verdict")
        for item_id in g.get("item_ids", []):
            verdict_of[item_id] = verdict
    rows = {}
    for it in case.get("items", []):
        key = _norm(it.get(id_field, it.get("item_id")))
        rows[key] = {"category": _norm(it.get("category")), "side": _norm(it.get("side")),
                     "verdict": _norm(verdict_of.get(it.get("item_id")))}
    return rows


def old_rows(records: list[dict], columns: dict[str, str]) -> dict[str, dict]:
    rows = {}
    for r in records:
        key = _norm(r.get(columns["id"]))
        if key:
            rows[key] = {f: _norm(r.get(columns[f])) for f in FIELDS}
    return rows


def compare(old: dict[str, dict], new: dict[str, dict]) -> list[dict]:
    """Every break where the two runs differ, or that only one run has."""
    diffs = []
    for key in sorted(old.keys() | new.keys()):
        a, b = old.get(key), new.get(key)
        if a is None or b is None:
            diffs.append({"id": key, "field": "presence",
                          "old": "present" if a else "missing", "helix": "present" if b else "missing"})
            continue
        for f in FIELDS:
            if a[f] != b[f]:
                diffs.append({"id": key, "field": f, "old": a[f] or "—", "helix": b[f] or "—"})
    return diffs


def _load_old(path: Path) -> list[dict]:
    text = path.read_text()
    if path.suffix.lower() == ".json":
        data = json.loads(text)
        return data["breaks"] if isinstance(data, dict) else data
    return list(csv.DictReader(text.splitlines()))


def _load_case(args) -> dict:
    if args.helix:
        return json.loads(Path(args.helix).read_text())
    req = urllib.request.Request(f"{args.api.rstrip('/')}/api/cases/{args.case_id}",
                                 headers={"X-Helix-User": args.user})
    with urllib.request.urlopen(req) as resp:  # noqa: S310 - an operator-given URL
        return json.loads(resp.read())


def _columns(spec: str | None) -> dict[str, str]:
    cols = {"id": "instrument", **{f: f for f in FIELDS}}
    for part in filter(None, (spec or "").split(",")):
        k, _, v = part.partition("=")
        if k.strip() not in cols or not v.strip():
            raise ValueError(f"bad --old-columns entry {part!r}; use id=…, category=…, side=…, verdict=…")
        cols[k.strip()] = v.strip()
    return cols


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    p.add_argument("--old", required=True, help="the old FOBO run: CSV or JSON, one row per break")
    p.add_argument("--old-columns", help='rename columns, e.g. "id=break_ref,side=origin"')
    src = p.add_mutually_exclusive_group(required=True)
    src.add_argument("--helix", help="a Helix case saved as JSON (GET /api/cases/<id>)")
    src.add_argument("--api", help="Helix base URL, with --case-id and --user")
    p.add_argument("--case-id")
    p.add_argument("--user")
    args = p.parse_args(argv)
    if args.api and not (args.case_id and args.user):
        p.error("--api needs --case-id and --user")
    try:
        old = old_rows(_load_old(Path(args.old)), _columns(args.old_columns))
        new = helix_rows(_load_case(args))
    except (OSError, ValueError, KeyError) as e:
        print(f"error: {e}", file=sys.stderr)
        return 2

    diffs = compare(old, new)
    print(f"old run: {len(old)} breaks · Helix: {len(new)} breaks · differences: {len(diffs)}")
    if diffs:
        print(f"\n{'break':<24} {'field':<10} {'old':<16} helix")
        for d in diffs:
            print(f"{d['id']:<24} {d['field']:<10} {d['old']:<16} {d['helix']}")
        return 1
    print("PASS: every break has the same category, side and verdict")
    return 0


if __name__ == "__main__":
    sys.exit(main())
