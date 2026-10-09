#!/usr/bin/env python3
"""Which upstream Agent One Finance version is this office copy?

    python3 which-version.py /path/to/office/repo

It compares the office's copy of the 124 files that changed upstream between
06 Oct (the office kit) and the latest version, file by file, with every
upstream version in between. It prints the closest version, the patch to
apply, and the files that differ from it (usually the office's own edits:
merge those by hand). It needs only Python 3, not git, and reads the files
without changing anything.
"""

import hashlib
import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent


def blob(data: bytes) -> str:
    """Git's blob id of the content (so it matches upstream without git)."""
    return hashlib.sha1(b"blob %d\0" % len(data) + data).hexdigest()


def ids(path: Path) -> set[str]:
    if not path.is_file():
        return set()
    data = path.read_bytes()
    return {blob(data), blob(data.replace(b"\r\n", b"\n"))}      # Windows line endings too


def main() -> None:
    if len(sys.argv) != 2:
        sys.exit(__doc__)
    repo = Path(sys.argv[1])
    if not (repo / "apps/backend/agent_one_finance").is_dir():
        sys.exit(f"{repo}: no apps/backend/agent_one_finance here. Is this the office's Agent One Finance repo? "
                 "If the office copy is still named Helix, use the upgrade-to-aof skill first.")
    table = json.loads((HERE / "versions.json").read_text())
    office = {f: ids(repo / f) for f in table["versions"][table["latest"]]["blobs"]}

    def score(v: str) -> tuple[int, list[str]]:
        differ = []
        for f, want in table["versions"][v]["blobs"].items():
            have = office[f]
            same = (want is None and not have) or (want is not None and want in have)
            if not same:
                differ.append(f)
        return len(office) - len(differ), differ

    scored = [(v, *score(v)) for v in table["order"]]
    best = max(scored, key=lambda s: (s[1], table["order"].index(s[0])))     # most files equal; latest on a tie
    v, hits, differ = best
    info = table["versions"][v]
    print(f"Closest upstream version: {v}  ({info['date']})  {info['title']}")
    print(f"  {hits} of {len(office)} files are exactly as upstream had them there.")
    print(f"  Its whats-new.md ends at section {info['section']}.")
    if v == table["latest"]:
        print("\nThe office is up to date. Nothing to apply.")
    else:
        print(f"\nApply: patches/from-{v}.patch   (git apply -3, see README.md)")
    if differ:
        print(f"\n{len(differ)} file(s) differ from {v}: office edits, or a copy in between. Check them by hand:")
        for f in differ:
            print("  ", f, "(missing in the office)" if not office[f] else "")
    print("\nHow close each version is (files equal):")
    for s in scored:
        print(f"  {s[0]}  {table['versions'][s[0]]['date']:>13}  {s[1]:3}  {table['versions'][s[0]]['title'][:70]}")


if __name__ == "__main__":
    main()
