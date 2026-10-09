#!/usr/bin/env python3
"""Bring Agent One Finance (AOF) from this repository into the office repos, the same way every time.

    python3 fobotower-main/office/aof_sync.py --upstream fobotower-main --workspace .            # report only
    python3 fobotower-main/office/aof_sync.py --upstream fobotower-main --workspace . --apply    # write

Run it from the workspace folder that holds the upstream download and the two office repos
(aos-frontend, aos-backend). It needs Python 3.9+ and git; nothing else, no network.

What it copies (see MAP, or aof-sync.json in the workspace to change it):
  - frontend: office/aos-frontend/src/app/finance -> aos-frontend/src/app/finance, already in the
    office's shape (Next.js pages under /finance, the console's code in the private folder _aof,
    JSX, scoped styles; made by apps/web/office/convert.mjs). Nothing else in aos-frontend is
    read or written;
  - backend: the AOF package, its migrations, configuration, documents and tests, into aos-backend.

For every file it compares three versions: upstream now, upstream at the last sync (the base),
and the office's file.
  - office file = base         -> take upstream (the office never changed it);
  - upstream now = base        -> keep the office file (only the office changed it);
  - both changed               -> three-way merge (git merge-file); a clash is marked in the file
                                  and listed in the report for a person to settle;
  - new upstream file          -> added;  removed upstream and unchanged in the office -> removed.
Files the office added itself are never touched; they are listed.

The base is kept in <workspace>/aof-sync-base, and each repo gets .aof-sync.json (what was synced,
with hashes). On the first sync there is no base yet; the download itself carries every earlier
release (office/aof-history.*), so the tool finds which release the office copied, updates the files
the office never touched, and merges the ones it edited. What is still different after that (the
hand-converted console) is replaced with --baseline once, after reviewing the report (see the
pack's README, office/README.md).
"""

from __future__ import annotations

import argparse
import fnmatch
import hashlib
import json
import re
import subprocess
import sys
import tarfile
import tempfile
import time
from pathlib import Path

MAP = {
    "frontend": {
        "repo": "aos-frontend",
        "roots": [["office/aos-frontend/src/app/finance", "src/app/finance"]],
        # The office's own files inside the synced folders: added once, never overwritten.
        "keep": ["src/app/finance/_aof/office/auth.js"],
        # Folders that hold only AOF, so files there that upstream does not have are leftovers of an
        # earlier conversion (removed by --baseline --prune).
        "owned": ["src/app/finance"],
    },
    "backend": {
        "repo": "aos-backend",
        "roots": [
            ["apps/backend/agent_one_finance", "agent_one_finance"],
            ["apps/backend/migrations", "aof_migrations"],
            ["config/agent-one-finance", "config/agent-one-finance"],
            ["apps/backend/seed_data/aof_documents", "seed_data/aof_documents"],
            ["apps/backend/tests/agent_one_finance", "tests/agent_one_finance"],
        ],
        "keep": ["config/agent-one-finance/connectors.yaml", "agent_one_finance/session_bridge.py"],
        "owned": [],
    },
}
IGNORE = ["*/__pycache__/*", "*.pyc", "*/.DS_Store", "*/node_modules/*"]
BASE_DIR = "aof-sync-base"
STATE = ".aof-sync.json"
CLASH = re.compile(r"^(<{7}|>{7}) ", re.M)


def sha(data: bytes) -> str:
    return hashlib.sha256(data.replace(b"\r\n", b"\n")).hexdigest()[:16]


def read(p: Path) -> bytes | None:
    return p.read_bytes() if p.is_file() else None


def files_under(root: Path) -> list[str]:
    if not root.is_dir():
        return []
    out = []
    for p in root.rglob("*"):
        rel = p.relative_to(root).as_posix()
        if p.is_file() and not any(fnmatch.fnmatch("/" + rel, pat) for pat in IGNORE):
            out.append(rel)
    return sorted(out)


class History:
    """Every earlier release of the synced files, shipped in the download (office/aof-history.*)."""

    def __init__(self, upstream: Path):
        index, blobs = upstream / "office/aof-history.json", upstream / "office/aof-history.tar.gz"
        self.versions = json.loads(index.read_text())["versions"] if index.is_file() else []
        self._tar = tarfile.open(blobs) if blobs.is_file() else None
        self.known: dict[str, set[str]] = {}
        for v in self.versions:
            for path, h in v["files"].items():
                self.known.setdefault(path, set()).add(h)

    def content(self, h: str) -> bytes | None:
        if self._tar is None:
            return None
        try:
            return self._tar.extractfile(h).read()
        except KeyError:
            return None

    def office_version(self, cfg: dict, repo: Path) -> dict | None:
        """The release the office copied: the one most of the office's files match (latest on a tie)."""
        best, best_n = None, 0
        for v in self.versions:
            n = 0
            for src, dst in cfg["roots"]:
                for path, h in v["files"].items():
                    if path.startswith(src + "/"):
                        office = read(repo / dst / path[len(src) + 1:])
                        n += office is not None and sha(office) == h
            if n >= best_n and n:
                best, best_n = v, n
        return best


def merge3(office: bytes, base: bytes, upstream: bytes) -> tuple[bytes, bool]:
    """git merge-file: (merged text, clean?)."""
    with tempfile.TemporaryDirectory() as d:
        paths = []
        for name, data in (("office", office), ("base", base), ("upstream", upstream)):
            p = Path(d, name)
            p.write_bytes(data)
            paths.append(str(p))
        r = subprocess.run(["git", "merge-file", "-p", "-L", "office", "-L", "last sync", "-L", "upstream", *paths],
                           capture_output=True)
        if r.returncode < 0 or r.returncode > 127:
            raise RuntimeError(r.stderr.decode())
        return r.stdout, r.returncode == 0


def plan_repo(name: str, cfg: dict, upstream: Path, ws: Path, baseline: bool, prune: bool, history: History) -> dict:
    repo = ws / cfg["repo"]
    if not repo.is_dir():
        return {"name": name, "repo": cfg["repo"], "missing": True, "actions": []}
    state_path = repo / STATE
    state = json.loads(state_path.read_text()) if state_path.is_file() else {"files": {}}
    known = state["files"]
    base_root = ws / BASE_DIR / cfg["repo"]
    copied = history.office_version(cfg, repo) if not known else None
    actions = []  # (kind, office path, upstream bytes or None, detail)
    seen = set()
    for src, dst in cfg["roots"]:
        for rel in files_under(upstream / src):
            o_path = f"{dst}/{rel}"
            seen.add(o_path)
            new = (upstream / src / rel).read_bytes()
            office = read(repo / o_path)
            base_sha = known.get(o_path)
            base = read(base_root / o_path)
            if base_sha is None and office is not None:
                # first sync: an earlier release the office file matches is its base (untouched);
                # otherwise the release the office copied is (the office edited the file)
                if sha(office) in history.known.get(f"{src}/{rel}", ()):
                    base, base_sha = office, sha(office)
                elif copied and f"{src}/{rel}" in copied["files"]:
                    base = history.content(copied["files"][f"{src}/{rel}"])
                    base_sha = sha(base) if base is not None else None
            if o_path in cfg["keep"]:
                if office is None:
                    actions.append(("add", o_path, new, "office file: added once, then the office's"))
                else:
                    kind = "same" if sha(office) == sha(new) else "keep-office"
                    actions.append((kind, o_path, None, "office file: never overwritten" if kind != "same" else ""))
            elif office is None:
                if base_sha and base_sha != sha(new):
                    actions.append(("clash", o_path, new, "removed in the office, changed upstream"))
                elif base_sha:
                    actions.append(("office-removed", o_path, None, "removed in the office; upstream unchanged"))
                else:
                    actions.append(("add", o_path, new, ""))
            elif sha(office) == sha(new):
                actions.append(("same", o_path, new, ""))
            elif base_sha is None:
                actions.append(("replace" if baseline else "differs", o_path, new,
                                "first sync: office file differs from upstream" + ("" if baseline else "; review, then --baseline")))
            elif sha(office) == base_sha:
                actions.append(("update", o_path, new, ""))
            elif sha(new) == base_sha:
                actions.append(("keep-office", o_path, None, "changed only in the office"))
            elif base is not None and sha(base) == base_sha:
                merged, clean = merge3(office, base, new)
                actions.append(("merge" if clean else "clash", o_path, merged,
                                "changed in both; merged" if clean else "changed in both; settle the marked lines"))
            else:
                actions.append(("clash", o_path, None, f"changed in both and the base is missing from {BASE_DIR}; merge by hand"))
    # upstream removed a file that was synced before
    for o_path, base_sha in known.items():
        if o_path in seen:
            continue
        office = read(repo / o_path)
        if office is None:
            continue
        if sha(office) == base_sha:
            actions.append(("remove", o_path, None, "removed upstream"))
        else:
            actions.append(("clash", o_path, None, "removed upstream, changed in the office; decide"))
    # office files in the synced folders that upstream does not have: the office's own, or (in
    # AOF-only folders) leftovers of an earlier conversion
    folders = sorted({d for _, d in cfg["roots"]} | set(cfg["owned"]))
    listed = set()
    for folder in folders:
        for rel in files_under(repo / folder):
            o_path = f"{folder}/{rel}"
            if o_path in seen or o_path in known or o_path in listed:
                continue
            listed.add(o_path)
            leftover = any(o_path.startswith(o + "/") for o in cfg["owned"]) and o_path not in cfg["keep"]
            if leftover and baseline and prune:
                actions.append(("remove", o_path, None, "leftover of an earlier conversion"))
            else:
                actions.append(("office-only", o_path, None, "not upstream: leftover of an earlier conversion?" if leftover else "the office's own file"))
    # office files the map does not cover are not looked at; the report says which folders were synced
    return {"name": name, "repo": cfg["repo"], "missing": False, "actions": actions, "state": state, "repo_path": repo,
            "base_root": base_root, "upstream_roots": cfg["roots"],
            "copied": f"{copied['version']} ({copied['date']})" if copied else None}


def apply(plan: dict, upstream: Path, label: str) -> None:
    repo, base_root, state = plan["repo_path"], plan["base_root"], plan["state"]
    for kind, o_path, data, _ in plan["actions"]:
        target = repo / o_path
        if kind in ("add", "update", "replace", "merge", "clash") and data is not None:
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_bytes(data)
        elif kind == "remove":
            target.unlink()
            state["files"].pop(o_path, None)
            (base_root / o_path).unlink(missing_ok=True)
            for d in target.parents:  # drop folders the removal emptied
                if d == repo or any(d.iterdir()):
                    break
                d.rmdir()
    # the new base: upstream as it is now, for every file this sync looked at
    for src, dst in plan["upstream_roots"]:
        for rel in files_under(upstream / src):
            o_path = f"{dst}/{rel}"
            acts = [x for x in plan["actions"] if x[1] == o_path]
            # not settled here: keep the old base, so the next sync shows them again
            if any(x[0] in ("differs", "office-removed") or (x[0] == "clash" and x[2] is None) for x in acts):
                continue
            data = (upstream / src / rel).read_bytes()
            (base_root / o_path).parent.mkdir(parents=True, exist_ok=True)
            (base_root / o_path).write_bytes(data)
            state["files"][o_path] = sha(data)
    state["synced_at"] = time.strftime("%Y-%m-%d %H:%M")
    state["upstream"] = label
    (repo / STATE).write_text(json.dumps(state, indent=1, sort_keys=True) + "\n")


def deps_report(upstream: Path, ws: Path) -> list[str]:
    """Backend packages upstream needs that the office's requirements file does not name."""
    py = read(upstream / "apps/backend/pyproject.toml")
    if py is None:
        return []
    block = re.search(r"^dependencies = \[(.*?)^\]", py.decode(), re.S | re.M)
    names = re.findall(r'"([A-Za-z0-9_.-]+)', block.group(1)) if block else []
    office = ""
    for f in ("requirements.txt", "app/requirements.txt", "requirements.in", "pyproject.toml"):
        office += (read(ws / "aos-backend" / f) or b"").decode(errors="ignore").lower()
    return [n for n in names if re.search(rf"(^|[\s\"']){re.escape(n.lower())}(\[|[\s=<>~!;\"']|$)", office, re.M) is None]


def frontend_deps(upstream: Path, ws: Path) -> list[str]:
    m = read(upstream / "office/aos-frontend/aof-frontend.json")
    pkg = read(ws / "aos-frontend/package.json")
    if m is None or pkg is None:
        return []
    have = json.loads(pkg)
    have = {**have.get("dependencies", {}), **have.get("devDependencies", {})}
    return [f"{n}@{v}" for n, v in json.loads(m)["dependencies"].items() if n not in have]


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--upstream", required=True, help="the upstream download (fobotower-main)")
    ap.add_argument("--workspace", default=".", help="the folder holding aos-frontend and aos-backend")
    ap.add_argument("--only", choices=["frontend", "backend"], help="sync one repo only")
    ap.add_argument("--apply", action="store_true", help="write the changes (default: report only)")
    ap.add_argument("--baseline", action="store_true", help="first sync only: take upstream for every file that differs")
    ap.add_argument("--prune", action="store_true", help="with --baseline: remove leftovers of an earlier conversion in AOF-only folders")
    ap.add_argument("--label", default="", help="the upstream version, for the record (e.g. the commit id on GitHub)")
    a = ap.parse_args()
    upstream, ws = Path(a.upstream).resolve(), Path(a.workspace).resolve()
    if not (upstream / "office/aos-frontend/aof-frontend.json").is_file():
        print(f"{upstream} is not the upstream repository (office/aos-frontend/aof-frontend.json missing)", file=sys.stderr)
        return 2
    cfg_file = ws / "aof-sync.json"
    mapping = json.loads(cfg_file.read_text()) if cfg_file.is_file() else MAP
    history = History(upstream)
    plans = [plan_repo(n, c, upstream, ws, a.baseline, a.prune, history) for n, c in mapping.items() if not a.only or a.only == n]

    lines = [f"# AOF sync report ({'applied' if a.apply else 'dry run'}, {time.strftime('%Y-%m-%d %H:%M')})", "",
             f"Upstream: `{upstream}` {a.label}", ""]
    blocked = False
    order = ["clash", "differs", "merge", "add", "update", "replace", "remove", "keep-office", "office-removed", "office-only", "same"]
    for p in plans:
        lines += [f"## {p['repo']}", ""]
        if p["missing"]:
            lines += [f"Not found in {ws}: skipped.", ""]
            continue
        lines += ["Synced folders: " + ", ".join(f"`{s}` → `{d}`" for s, d in p["upstream_roots"]), ""]
        if p["copied"]:
            lines += [f"First sync: the office copy matches the AOF release of {p['copied']} most closely.", ""]
        counts = {k: sum(1 for x in p["actions"] if x[0] == k) for k in order}
        lines += ["| " + " | ".join(k for k in order if counts[k]) + " |", "|" + "---|" * sum(1 for k in order if counts[k]),
                  "| " + " | ".join(str(counts[k]) for k in order if counts[k]) + " |", ""]
        for kind in order[:-1]:
            rows = [x for x in p["actions"] if x[0] == kind]
            if rows:
                lines += [f"### {kind} ({len(rows)})", ""] + [f"- `{x[1]}`" + (f": {x[3]}" if x[3] else "") for x in rows] + [""]
        if counts["differs"] and not a.baseline:
            blocked = True
        markers = [x[1] for x in p["actions"] if x[0] != "remove" and (p["repo_path"] / x[1]).is_file()
                   and CLASH.search((p["repo_path"] / x[1]).read_text(errors="ignore"))]
        if markers:
            blocked = True
            lines += ["### Unsettled merge marks from the last sync", ""] + [f"- `{m}`" for m in markers] + [""]
    missing_py = deps_report(upstream, ws)
    missing_js = frontend_deps(upstream, ws)
    if missing_py or missing_js:
        lines += ["## Packages to add", ""]
        lines += [f"- aos-backend: `{n}`" for n in missing_py] + [f"- aos-frontend: `{n}`" for n in missing_js] + [""]
    report = ws / "aof-sync-report.md"
    report.write_text("\n".join(lines))
    print("\n".join(lines))
    if a.apply:
        if blocked:
            print("\nNot applied: settle the marked files, or review the first-sync differences and rerun with --baseline.", file=sys.stderr)
            return 1
        for p in plans:
            if not p["missing"]:
                apply(p, upstream, a.label)
        print(f"\nApplied. Report: {report}")
    else:
        print(f"\nDry run. Report: {report}. Rerun with --apply to write.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
