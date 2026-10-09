#!/usr/bin/env python3
"""Record every released version of the files aof_sync.py copies, so the sync can work from the
fobotower-main download alone (no second, older download).

    python3 office/build_history.py            # rebuild office/aof-history.*
    python3 office/build_history.py --check    # fail if a released version is missing

Writes two files beside this script:
  aof-history.json    every version (commit) since AOF got its name, with each synced file's hash;
  aof-history.tar.gz  the content of each distinct file version, named by its hash.

With them, aof_sync.py tells an untouched old AOF file (its hash is a released version: safe to
update) from a file the office edited (no released version matches: merged against the version the
office copied). Run it in this repository, with its git history, after any change to a synced file;
a test fails if it is out of date.
"""

from __future__ import annotations

import argparse
import gzip
import importlib.util
import io
import json
import subprocess
import sys
import tarfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
SINCE = "c762a2b"  # 6 Oct 2026: the first version under the Agent One Finance names
INDEX, BLOBS = HERE / "aof-history.json", HERE / "aof-history.tar.gz"

spec = importlib.util.spec_from_file_location("aof_sync", HERE / "aof_sync.py")
aof_sync = importlib.util.module_from_spec(spec)
spec.loader.exec_module(aof_sync)


def git(*args: str, binary: bool = False):
    out = subprocess.run(["git", "-C", str(ROOT), *args], capture_output=True, check=True).stdout
    return out if binary else out.decode()


def roots() -> list[str]:
    return sorted({src for cfg in aof_sync.MAP.values() for src, _ in cfg["roots"]})


def collect() -> tuple[list[dict], dict[str, bytes]]:
    """Every commit since SINCE that changed a synced file, and the working tree (the release being
    made): its synced files and their hashes."""
    commits = git("rev-list", "--reverse", f"{SINCE}^..HEAD", "--", *roots()).split()
    versions, contents, by_blob = [], {}, {}
    for c in commits:
        files = {}
        for line in git("ls-tree", "-r", c, "--", *roots()).splitlines():
            meta, path = line.split("\t", 1)
            if any(Path("/" + path).match(p) for p in aof_sync.IGNORE):
                continue
            blob = meta.split()[2]
            if blob not in by_blob:
                data = git("cat-file", "blob", blob, binary=True)
                by_blob[blob] = aof_sync.sha(data)
                contents[by_blob[blob]] = data
            files[path] = by_blob[blob]
        versions.append({"version": c[:7], "date": git("log", "-1", "--format=%cs", c).strip(), "files": files})
    files = {}
    for path in git("ls-files", "--cached", "--others", "--exclude-standard", "--", *roots()).splitlines():
        if (ROOT / path).is_file() and not any(Path("/" + path).match(p) for p in aof_sync.IGNORE):
            data = (ROOT / path).read_bytes()
            h = aof_sync.sha(data)
            contents[h] = data
            files[path] = h
    if not versions or files != versions[-1]["files"]:
        versions.append({"version": "this release", "date": git("log", "-1", "--format=%cs").strip(), "files": files})
    return versions, contents


def write(versions: list[dict], contents: dict[str, bytes]) -> None:
    INDEX.write_text(json.dumps({"since": SINCE, "versions": versions}, indent=0, sort_keys=True) + "\n")
    buf = io.BytesIO()
    with tarfile.open(fileobj=buf, mode="w", format=tarfile.PAX_FORMAT) as tar:
        for name in sorted(contents):
            info = tarfile.TarInfo(name)
            info.size, info.mtime, info.mode = len(contents[name]), 0, 0o644
            tar.addfile(info, io.BytesIO(contents[name]))
    BLOBS.write_bytes(gzip.compress(buf.getvalue(), mtime=0))  # same input, same bytes


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--check", action="store_true", help="fail if a released version is missing")
    a = ap.parse_args()
    versions, contents = collect()
    if a.check:
        # by content, not commit id: a commit cannot name itself, but its files are in the history
        have = json.loads(INDEX.read_text())["versions"] if INDEX.is_file() else []
        recorded = {(p, h) for v in have for p, h in v["files"].items()}
        missing = sorted({p for v in versions for p, h in v["files"].items() if (p, h) not in recorded})
        if missing:
            print(f"office/aof-history is missing versions of {len(missing)} file(s), e.g. {missing[0]}. "
                  "Run: python3 office/build_history.py", file=sys.stderr)
            return 1
        print(f"office/aof-history is up to date ({len(versions)} versions)")
        return 0
    write(versions, contents)
    print(f"{len(versions)} versions, {len(contents)} file versions, {BLOBS.stat().st_size // 1024} KB")
    return 0


if __name__ == "__main__":
    sys.exit(main())
