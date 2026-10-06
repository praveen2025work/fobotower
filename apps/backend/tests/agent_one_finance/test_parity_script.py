"""The FOBO → Agent One Finance parity script compares break by break."""

import importlib.util
import json
from pathlib import Path

SCRIPT = Path(__file__).resolve().parents[2] / "scripts" / "fobo_aof_parity.py"
spec = importlib.util.spec_from_file_location("fobo_aof_parity", SCRIPT)
parity = importlib.util.module_from_spec(spec)
spec.loader.exec_module(parity)

CASE = {
    "id_field": "instrument",
    "items": [
        {"item_id": "i1", "instrument": "EURUSD FWD", "category": "C", "side": "BO"},
        {"item_id": "i2", "instrument": "UST 2Y", "category": "A", "side": "FO"},
        {"item_id": "i3", "instrument": "GILT 30Y", "category": None, "side": None},  # out of scope
    ],
    "groups": [
        {"item_ids": ["i1"], "finding": {"verdict": "POST"}},
        {"item_ids": ["i2"], "finding": {"verdict": "DO_NOT_POST"}},
    ],
}


def test_same_answers_pass(tmp_path, capsys):
    (tmp_path / "case.json").write_text(json.dumps(CASE))
    (tmp_path / "old.csv").write_text(
        "break_ref,category,side,verdict\n"
        "EURUSD FWD,C,BO,post\nUST 2Y,A,FO,DO_NOT_POST\nGILT 30Y,,,\n")
    code = parity.main(["--old", str(tmp_path / "old.csv"), "--old-columns", "id=break_ref",
                        "--aof", str(tmp_path / "case.json")])
    assert code == 0
    assert "PASS" in capsys.readouterr().out


def test_differences_and_missing_breaks_fail(tmp_path, capsys):
    (tmp_path / "case.json").write_text(json.dumps(CASE))
    (tmp_path / "old.json").write_text(json.dumps({"breaks": [
        {"instrument": "EURUSD FWD", "category": "C", "side": "BO", "verdict": "POST"},
        {"instrument": "UST 2Y", "category": "A", "side": "BO", "verdict": "POST"},
        {"instrument": "JGB 10Y", "category": "H", "side": "UNKNOWN", "verdict": "ESCALATE"},
    ]}))
    code = parity.main(["--old", str(tmp_path / "old.json"), "--aof", str(tmp_path / "case.json")])
    out = capsys.readouterr().out
    assert code == 1
    diffs = parity.compare(parity.old_rows(json.loads((tmp_path / "old.json").read_text())["breaks"],
                                           parity._columns(None)), parity.aof_rows(CASE))
    assert {(d["id"], d["field"]) for d in diffs} == {
        ("UST 2Y", "side"), ("UST 2Y", "verdict"), ("JGB 10Y", "presence"), ("GILT 30Y", "presence")}
    assert "differences: 4" in out


def test_bad_column_spec_is_an_input_error(tmp_path):
    (tmp_path / "old.csv").write_text("instrument\n")
    (tmp_path / "case.json").write_text("{}")
    assert parity.main(["--old", str(tmp_path / "old.csv"), "--old-columns", "nope=x",
                        "--aof", str(tmp_path / "case.json")]) == 2
