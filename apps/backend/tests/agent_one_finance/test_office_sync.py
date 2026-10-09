"""office/aof_sync.py: every case of the three-way sync into the office repos."""

import importlib.util
import json
import subprocess
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[4]
spec = importlib.util.spec_from_file_location("aof_sync", ROOT / "office" / "aof_sync.py")
aof_sync = importlib.util.module_from_spec(spec)
spec.loader.exec_module(aof_sync)

pytestmark = pytest.mark.skipif(subprocess.run(["git", "--version"], capture_output=True).returncode, reason="needs git")


def write(base: Path, files: dict[str, str]) -> None:
    for rel, text in files.items():
        p = base / rel
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(text)


def upstream(ws: Path, name: str, backend: dict[str, str], frontend: dict[str, str] | None = None) -> Path:
    up = ws / name
    write(up, {"office/aos-frontend/aof-frontend.json": json.dumps({"dependencies": {}})})
    write(up, {f"apps/backend/agent_one_finance/{k}": v for k, v in backend.items()})
    write(up, {f"office/aos-frontend/src/components/financeagent/{k}": v for k, v in (frontend or {}).items()})
    return up


def sync(ws: Path, up: Path, *extra: str) -> int:
    import sys

    argv = sys.argv
    sys.argv = ["aof_sync.py", "--upstream", str(up), "--workspace", str(ws), *extra]
    try:
        return aof_sync.main()
    finally:
        sys.argv = argv


def report(ws: Path) -> str:
    return (ws / "aof-sync-report.md").read_text()


LLM = "line 1\nline 2\nline 3\nline 4\nline 5\nline 6\n"


def test_first_sync_needs_review_then_baseline_replaces_and_prunes(tmp_path):
    up = upstream(tmp_path, "up1", {"a.py": "new a\n"}, {"pages/Overview.jsx": "upstream page\n"})
    write(tmp_path / "aos-backend", {"agent_one_finance/a.py": "office a\n", "agent_one_finance/bridge.py": "ours\n"})
    write(tmp_path / "aos-frontend", {"src/components/financeagent/pages/Overview.jsx": "hand converted\n",
                                      "src/components/financeagent/ui/Button.jsx": "old split\n", "src/app/page.jsx": "agent one\n"})
    assert sync(tmp_path, up, "--apply") == 1  # differences need a look first
    assert "first sync" in report(tmp_path) and "the office's own file" in report(tmp_path)
    assert sync(tmp_path, up, "--apply", "--baseline", "--prune") == 0
    fe = tmp_path / "aos-frontend/src"
    assert (fe / "components/financeagent/pages/Overview.jsx").read_text() == "upstream page\n"
    assert not (fe / "components/financeagent/ui").exists()  # leftover of the hand conversion, and its folder
    assert (fe / "app/page.jsx").read_text() == "agent one\n"  # outside the AOF folders: never looked at
    assert (tmp_path / "aos-backend/agent_one_finance/bridge.py").read_text() == "ours\n"  # office file kept
    assert json.loads((tmp_path / "aos-backend/.aof-sync.json").read_text())["files"]["agent_one_finance/a.py"]


def test_later_syncs_update_keep_merge_clash_and_remove(tmp_path):
    up1 = upstream(tmp_path, "up1", {"same.py": "s\n", "keep.py": "k\n", "llm.py": LLM, "clash.py": "c\n", "gone.py": "g\n"})
    write(tmp_path / "aos-backend", {f"agent_one_finance/{k}": (up1 / "apps/backend/agent_one_finance" / k).read_text()
                                     for k in ("same.py", "keep.py", "llm.py", "clash.py", "gone.py")})
    assert sync(tmp_path, up1, "--apply") == 0
    office = tmp_path / "aos-backend/agent_one_finance"
    # the office edits three files
    (office / "keep.py").write_text("k office\n")
    (office / "llm.py").write_text(LLM.replace("line 1", "line 1 office"))
    (office / "clash.py").write_text("c office\n")
    # upstream moves on
    up2 = upstream(tmp_path, "up2", {"same.py": "s v2\n", "keep.py": "k\n", "llm.py": LLM.replace("line 6", "line 6 v2"),
                                     "clash.py": "c v2\n", "new.py": "n\n"})
    assert sync(tmp_path, up2, "--apply") == 0
    assert (office / "same.py").read_text() == "s v2\n"  # untouched in the office: updated
    assert (office / "keep.py").read_text() == "k office\n"  # only the office changed it: kept
    assert (office / "llm.py").read_text() == LLM.replace("line 1", "line 1 office").replace("line 6", "line 6 v2")  # merged
    assert "<<<<<<< office" in (office / "clash.py").read_text()  # both changed the same line: marked
    assert (office / "new.py").read_text() == "n\n" and not (office / "gone.py").exists()
    text = report(tmp_path)
    assert "### clash (1)" in text and "### merge (1)" in text
    # unsettled marks block the next sync until a person settles them
    assert sync(tmp_path, up2, "--apply") == 1
    (office / "clash.py").write_text("c settled\n")
    assert sync(tmp_path, up2, "--apply") == 0
    assert "changed only in the office" in report(tmp_path)


def test_first_sync_with_base_from_merges_instead_of_replacing(tmp_path):
    old = upstream(tmp_path, "old", {"llm.py": LLM, "env.py": "e1\n"})
    new = upstream(tmp_path, "new", {"llm.py": LLM, "env.py": "e2\n"})
    write(tmp_path / "aos-backend", {"agent_one_finance/llm.py": "# office\n" + LLM, "agent_one_finance/env.py": "e1\n"})
    assert sync(tmp_path, new, "--apply", "--base-from", str(old), "--only", "backend") == 0
    office = tmp_path / "aos-backend/agent_one_finance"
    assert (office / "llm.py").read_text().startswith("# office") and (office / "env.py").read_text() == "e2\n"
