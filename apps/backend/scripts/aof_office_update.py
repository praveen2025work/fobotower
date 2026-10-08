"""Build the office update package: a patch from every recent upstream version
to the latest, and the table `which-version.py` uses to find the office's version.

    python apps/backend/scripts/aof_office_update.py [--since c762a2b] [--to HEAD] [--out aof-update]

Run it in this repo, on a machine with the full git history. Zip the output
folder and carry it into the office the approved way. The office then follows
docs/agent-one-finance/migration/office-update/README.md. Demo screenshots and
PDFs are left out of the patches.
"""

import argparse
import json
import shutil
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
KIT = ROOT / "docs/agent-one-finance/migration/office-update"
EXCLUDE = ":!docs/agent-one-finance/demo"
WHATS_NEW = "docs/agent-one-finance/migration/whats-new.md"


def git(*args: str) -> str:
    return subprocess.run(["git", "-C", str(ROOT), *args], capture_output=True, text=True, check=True).stdout


def section(commit: str) -> str:
    """The last `## 1…` section of whats-new.md at that version (what the office can read by hand)."""
    try:
        text = git("show", f"{commit}:{WHATS_NEW}")
    except subprocess.CalledProcessError:
        return "none"
    found = [line[3:].split(".")[0] for line in text.splitlines() if line.startswith("## 1")]
    return found[-1] if found else "none"


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--since", default="c762a2b", help="oldest office version supported (default: the office kit, 06 Oct)")
    ap.add_argument("--to", default="HEAD", help="the version to bring the office to (default: HEAD)")
    ap.add_argument("--out", default="aof-update", help="output folder")
    a = ap.parse_args()
    out = Path(a.out).resolve()
    if out.exists():
        shutil.rmtree(out)
    (out / "patches").mkdir(parents=True)
    to = git("rev-parse", "--short=7", a.to).strip()
    commits = git("rev-list", "--first-parent", "--reverse", f"{a.since}^..{to}").split()
    files = git("diff", "--name-only", f"{a.since}^", to, "--", ".", EXCLUDE).split()
    versions = {}
    for c in commits:
        short = c[:7]
        blobs = {}
        for line in git("ls-tree", "-r", c, "--", *files).splitlines():
            meta, path = line.split("\t")
            blobs[path] = meta.split()[2]
        versions[short] = {"date": git("log", "-1", "--format=%ad", "--date=format:%d %b %H:%M", c).strip(),
                           "title": git("log", "-1", "--format=%s", c).strip(), "section": section(c),
                           "blobs": {f: blobs.get(f) for f in files}}
        if short != to:
            (out / "patches" / f"from-{short}.patch").write_text(git("diff", "--binary", c, to, "--", ".", EXCLUDE))
    (out / "versions.json").write_text(json.dumps({"latest": to, "order": [c[:7] for c in commits], "versions": versions}))
    shutil.copy(KIT / "which-version.py", out / "which-version.py")
    shutil.copy(KIT / "README.md", out / "README.md")
    print(f"{out}: {len(commits)} versions ({commits[0][:7]} … {to}), {len(files)} files, {len(commits) - 1} patches")


if __name__ == "__main__":
    main()
