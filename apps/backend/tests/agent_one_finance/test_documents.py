"""The documents service (PDF and Excel in, PDF reports out) and the report
validation capability built on it: Excel vs the ledger, four-eyes, a PDF."""

import dataclasses
import io

import pytest
from pypdf import PdfReader

from agent_one_finance import gateway
from agent_one_finance.capabilities import seed_files
from agent_one_finance.config import settings
from agent_one_finance.entitlement import Caller
from agent_one_finance.manifest import Manifest, problems
from agent_one_finance.mcp_services import documents

REPORT = "report.validation"
KEY = {"entity": "UK01", "period": "2026-09", "report": "mgmt-report-2026-09.xlsx"}


@pytest.fixture(autouse=True, params=["db", "fs"])
def reports_store(request, tmp_path, monkeypatch):
    """Every test runs against both report stores."""
    patched = dataclasses.replace(settings(), reports_dir=tmp_path, reports_store=request.param)
    monkeypatch.setattr(documents, "settings", lambda: patched)
    return request.param


def _ctx(user="alice", scopes=("UK01",), requested_by="match", tools=None):
    caller = Caller(user, frozenset({"FIN_PREPARER"}), {"entity": frozenset(scopes)})
    return gateway.CallContext(capability_id=REPORT, caller=caller, requested_by=requested_by,
                               allowed_tools=frozenset(tools or gateway.registry().all_tools()))


# ---------- the service, through the gateway ----------

async def test_reads_an_excel_workbook_by_its_header_row():
    out = await gateway.call(_ctx(), "documents.read_workbook",
                             {"entity": "UK01", "name": KEY["report"]})
    assert out["columns"] == ["account", "account_name", "cost_centre", "actual"]
    assert {"account": "6900", "account_name": "Restructuring", "cost_centre": "CC10",
            "actual": 40000} in out["rows"]


async def test_reads_a_pdf_page_by_page():
    out = await gateway.call(_ctx(), "documents.read_pdf",
                             {"entity": "UK01", "name": "mgmt-commentary-2026-09.pdf"})
    assert out["pages"] == 1 and "25,000.00 accrual" in out["rows"][0]["text"]


async def test_documents_are_scoped_and_paths_cannot_escape():
    with pytest.raises(gateway.ToolDenied, match="not entitled to entity=US01"):
        await gateway.call(_ctx(), "documents.list_documents", {"entity": "US01"})
    with pytest.raises(gateway.ToolFailed, match="invalid document name"):
        await gateway.call(_ctx(), "documents.read_pdf", {"entity": "UK01", "name": "../US01/x.pdf"})


async def test_writing_a_report_is_publish_only():
    args = {"entity": "UK01", "name": "x", "title": "t"}
    for requested_by in ("match", "llm"):
        with pytest.raises(gateway.ToolDenied, match="only the publish step"):
            await gateway.call(_ctx(requested_by=requested_by), "documents.render_pdf_report", args)


# ---------- report validation, end to end ----------

async def _validated(api, user="alice"):
    case = (await api.post(f"/api/capabilities/{REPORT}/cases", json={"case_key": KEY},
                           headers=api.as_user(user))).json()
    assert case["status"] == "awaiting_review", case
    for g in case["groups"]:
        res = await api.post(f"/api/cases/{case['case_id']}/decisions", headers=api.as_user(user),
                             json={"group_id": g["group_id"], "action": "approve",
                                   "idempotency_key": f"{case['case_id']}-{g['group_id']}"})
        assert res.status_code == 201, res.text
        last = res.json()
    return case, last["case"]


async def test_report_lines_are_matched_to_the_ledger(api):
    case, _ = await _validated(api)
    breaks = {(i["account"], i["cost_centre"]): i for i in case["items"]}
    assert set(breaks) == {("6300", "CC10"), ("4000", "CC20"), ("7200", "CC20"), ("6900", "CC10")}
    assert breaks[("6300", "CC10")]["difference"] == 25000.0
    assert breaks[("7200", "CC20")]["break_type"] == "missing_report"
    assert breaks[("6900", "CC10")]["break_type"] == "missing_ledger"
    assert all(g["finding"]["status"] == "proposed" for g in case["groups"]), case["groups"]
    rounding = next(g for g in case["groups"] if g["group_key"] == {"account": "4000"})
    assert rounding["finding"]["rule"] == "rounding"


async def test_released_validation_publishes_one_pdf_report(api):
    _, reviewed = await _validated(api)
    assert reviewed["status"] == "awaiting_publish" and reviewed["documents"] == []
    with pytest.raises(documents.DocumentError):                      # nothing before release
        await documents.load_report("UK01", f"{reviewed['case_id']}.pdf")

    res = await api.post(f"/api/cases/{reviewed['case_id']}/publish", headers=api.as_user("bob"),
                         json={"idempotency_key": "release-report-1"})
    assert res.status_code == 201, res.text
    done = res.json()["case"]
    assert (done["status"], done["outcome"]) == ("completed", "published")
    [doc] = done["documents"]
    assert doc["name"] == f"{done['case_id']}.pdf" and doc["pages"] >= 1

    content, content_type = await documents.load_report("UK01", doc["name"])
    assert content_type == "application/pdf"
    text = "\n".join(p.extract_text() for p in PdfReader(io.BytesIO(content)).pages)
    assert "Report validation" in text and "mgmt-report-2026-09.xlsx" in text
    assert "account 6300" in text and "account 6900" in text
    assert "release" in text and "bob" in text and "alice" in text   # the sign-off block

    got = await api.get(doc["url"], headers=api.as_user("bob"))
    assert got.status_code == 200 and got.content.startswith(b"%PDF")
    assert (await api.get(doc["url"], headers=api.as_user("viewer"))).status_code == 404
    assert (await api.get(f"/api/cases/{done['case_id']}/documents/other.pdf",
                          headers=api.as_user("bob"))).status_code == 404


def _report(**changes) -> list[str]:
    m = next(m for m in seed_files() if m.id == REPORT).model_dump(by_alias=True)
    return problems(Manifest.model_validate({**m, **changes}))


def test_publish_tokens_must_match_per():
    base = next(m for m in seed_files() if m.id == REPORT).model_dump(by_alias=True)
    assert _report() == []
    found = _report(publish={**base["publish"], "per": "group"})
    assert "publish.args.sections: `$approved` cannot be used with per: group" in found
    found = _report(publish={**base["publish"], "args": {**base["publish"]["args"], "x": "$comment"}})
    assert "publish.args.x: `$comment` cannot be used with per: case" in found
    match = {**base["match"], "left": {"tool": "documents.render_pdf_report", "args": {}}}
    assert ("tool `documents.render_pdf_report` writes to a bank system; only `publish` may use it"
            in _report(match=match))
