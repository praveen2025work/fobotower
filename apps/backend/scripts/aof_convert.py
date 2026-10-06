"""Rename a Helix-named copy of the platform to the Agent One Finance names.

For the office repo: run it over the office copy (or over just the office's own files) before
bringing in the upstream changes, so both sides use the same names. The rules live in
docs/agent-one-finance/migration/rename-map.json; this script only applies them.

    # see what would change (nothing is written)
    python apps/backend/scripts/aof_convert.py --root /path/to/office-repo
    # do it
    python apps/backend/scripts/aof_convert.py --root /path/to/office-repo --apply
    # only some files (e.g. the office's own connectors, adapter and config)
    python apps/backend/scripts/aof_convert.py --root . --apply --only config/helix/connectors.yaml ...

Moves use `git mv` when the root is a git checkout, so history follows the files. Old Alembic
migrations, lock files, binaries and this kit's own notes are left alone, and so is any line
that carries "aof-convert: keep". At the end it lists every remaining
"helix" mention so a person can decide each one. Running it twice changes nothing.
"""

from __future__ import annotations

import argparse
import json
import os
import re
import subprocess
import sys
from pathlib import Path

MAP = Path(__file__).resolve().parents[3] / "docs" / "agent-one-finance" / "migration" / "rename-map.json"
PACKAGE = "apps/backend/agent_one_finance"
KEEP = "aof-convert: keep"  # a line carrying this is left as it is


def load(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def is_git(root: Path) -> bool:
    return subprocess.run(["git", "-C", str(root), "rev-parse"], capture_output=True).returncode == 0


def tracked(root: Path, git: bool) -> list[str]:
    if git:
        out = subprocess.run(["git", "-C", str(root), "ls-files", "-co", "--exclude-standard"],
                             capture_output=True, text=True, check=True).stdout
        return sorted({f for f in out.splitlines() if f and (root / f).exists()})
    return sorted(str(p.relative_to(root)).replace(os.sep, "/") for p in root.rglob("*") if p.is_file())


def move(root: Path, a: str, b: str, git: bool, apply: bool, log: list[str]) -> None:
    src, dst = root / a, root / b
    if not src.exists():
        return
    if dst.exists():
        # The folder is already there (e.g. the conversion kit was copied into
        # docs/agent-one-finance first): move file by file, never overwrite.
        if src.is_dir() and dst.is_dir():
            for f in sorted(p for p in src.rglob("*") if p.is_file() and "__pycache__" not in p.parts):
                rel = f.relative_to(src)
                if (dst / rel).exists():
                    log.append(f"keep  {a}/{rel} (already at {b}/{rel}; compare them by hand)")
                else:
                    move(root, f"{a}/{rel}".replace(os.sep, "/"), f"{b}/{rel}".replace(os.sep, "/"), git, apply, log)
            if apply:  # drop the folders left empty
                for d in sorted((p for p in src.rglob("*") if p.is_dir()), key=lambda p: len(p.parts), reverse=True):
                    if not any(d.iterdir()):
                        d.rmdir()
                if not any(src.iterdir()):
                    src.rmdir()
        return
    log.append(f"move  {a} -> {b}")
    if not apply:
        return
    dst.parent.mkdir(parents=True, exist_ok=True)
    if git and subprocess.run(["git", "-C", str(root), "mv", a, b], capture_output=True).returncode == 0:
        return
    src.rename(dst)


def modules(root: Path) -> list[str]:
    """Names under the package, so `helix.steps` becomes `agent_one_finance.steps` while
    `helix.allowed` (a trace attribute) becomes `aof.allowed`."""
    names = {"web", "config", "mcp_services", "stub_connectors"}
    for base in (root / PACKAGE, root / "apps/backend/helix"):
        if base.is_dir():
            names |= {p.stem for p in base.iterdir() if p.suffix == ".py" or (p.is_dir() and not p.name.startswith("__"))}
    return sorted(names - {"__init__"}, key=len, reverse=True)


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--root", default=".", help="the repo to convert")
    ap.add_argument("--map", default=str(MAP), help="the rename map (default: the one in this repo)")
    ap.add_argument("--apply", action="store_true", help="write the changes (default: dry run)")
    ap.add_argument("--only", nargs="*", help="limit content changes to these paths (relative to --root)")
    args = ap.parse_args()

    root = Path(args.root).resolve()
    m = load(Path(args.map))
    git = is_git(root)
    skip = [re.compile(s) for s in m["skip"]]
    no_text = [re.compile(s) for s in m.get("skip_text", [])]
    skipped = lambda f: any(s.search(f) for s in skip)
    binary = lambda f: skipped(f) or any(s.search(f) for s in no_text)
    log: list[str] = []

    # 1. folders and known files
    if not args.only:
        for a, b in m["moves"]:
            move(root, a, b, git, args.apply, log)
        # 2. any other file whose name still says helix
        for f in tracked(root, git):
            if skipped(f) or "helix" not in Path(f).name.lower():
                continue
            name = Path(f).name
            new = name
            for a, b in m["file_names"]:
                new = new.replace(a, b)
            if Path(name).stem.lower() == "helix":
                new = "aof" + Path(name).suffix
            if new != name:
                move(root, f, str(Path(f).with_name(new)).replace(os.sep, "/"), git, args.apply, log)

    # 3. text
    mods = "|".join(map(re.escape, modules(root)))
    patterns = [(re.compile(p.replace("{modules}", mods)), r) for p, r in m["patterns"]]
    files = tracked(root, git)
    if args.only:
        wanted = {str(Path(p)).replace(os.sep, "/") for p in args.only}
        files = [f for f in files if f in wanted or any(f.startswith(w.rstrip("/") + "/") for w in wanted)]
    changed = 0
    for f in files:
        if binary(f):
            continue
        path = root / f
        try:
            text = path.read_text(encoding="utf-8")
        except (UnicodeDecodeError, OSError):
            continue
        out = []
        for line in text.splitlines(keepends=True):
            if KEEP not in line:
                for a, b in m["literal"]:
                    line = line.replace(a, b)
                for rx, b in patterns:
                    line = rx.sub(b, line)
            out.append(line)
        new = "".join(out)
        if new != text:
            changed += 1
            n = sum(1 for x, y in zip(text.splitlines(), new.splitlines()) if x != y)
            log.append(f"edit  {f} ({n} lines)")
            if args.apply:
                path.write_text(new, encoding="utf-8")

    # 4. what is left for a person to decide
    left: list[str] = []
    for f in tracked(root, git):
        if binary(f):
            continue
        try:
            lines = (root / f).read_text(encoding="utf-8").splitlines()
        except (UnicodeDecodeError, OSError):
            continue
        left += [f"{f}:{i}: {l.strip()[:120]}" for i, l in enumerate(lines, 1) if "helix" in l.lower() and KEEP not in l]

    print("\n".join(log) or "nothing to move or edit")
    print(f"\n{'applied' if args.apply else 'dry run'}: {sum(l.startswith('move') for l in log)} moves, {changed} files edited")
    if not args.apply:
        print("(run again with --apply to write; a dry run does not show edits inside files that would move)")
    if left:
        print(f"\n{len(left)} lines still mention helix (old migrations and renaming notes are expected; decide the rest):")
        print("\n".join(left[:200]))
    return 0


if __name__ == "__main__":
    sys.exit(main())
