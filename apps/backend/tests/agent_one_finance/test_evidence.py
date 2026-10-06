"""Evidence uploaded into a case (readable by the document tools, audited)
and the evidence pack an auditor takes away."""

import io

from pypdf import PdfReader

from agent_one_finance import gateway
from agent_one_finance.entitlement import Caller
from tests.agent_one_finance.conftest import VARIANCE

KEY = {"entity": "UK01", "period": "2026-09"}
PDF = open("/home/user/fobotower/apps/backend/seed_data/aof_documents/UK01/mgmt-commentary-2026-09.pdf", "rb").read()


async def _case(api):
    return (await api.post(f"/api/capabilities/{VARIANCE}/cases", json={"case_key": KEY},
                           headers=api.as_user("alice"))).json()


async def _upload(api, case_id, user="alice", name="accrual support.pdf", content=PDF):
    return await api.post(f"/api/cases/{case_id}/evidence", headers=api.as_user(user),
                          files={"file": (name, content, "application/pdf")}, data={"note": "IT accrual"})


async def test_a_reviewer_uploads_evidence_and_the_document_tools_can_read_it(api):
    case = await _case(api)
    res = await _upload(api, case["case_id"])
    assert res.status_code == 201, res.text
    body = res.json()
    [ev] = body["case"]["evidence"]
    assert ev["name"] == f"{case['case_id']}--accrual support.pdf" and ev["uploaded_by"] == "alice"
    caller = Caller("alice", frozenset({"FIN_PREPARER"}), {"entity": frozenset({"UK01"})})
    ctx = gateway.CallContext(capability_id=VARIANCE, caller=caller, requested_by="llm",
                              allowed_tools=frozenset({"documents.list_documents", "documents.read_pdf"}))
    listed = await gateway.call(ctx, "documents.list_documents", {"entity": "UK01"})
    assert any(r["name"] == ev["name"] and r["source"] == "uploaded" for r in listed["rows"])
    text = await gateway.call(ctx, "documents.read_pdf", {"entity": "UK01", "name": ev["name"]})
    assert "25,000.00 accrual" in text["rows"][0]["text"]
    got = await api.get(ev["url"], headers=api.as_user("bob"))
    assert got.status_code == 200 and got.content == PDF
    audit = (await api.get("/api/audit", headers=api.as_user("bob"))).json()
    assert any(e["kind"] == "evidence" and e["actor"] == "alice" for e in audit)


async def test_only_real_pdfs_and_workbooks_from_people_on_the_case(api):
    case = await _case(api)
    assert (await _upload(api, case["case_id"], name="x.exe", content=b"MZ")).status_code == 409
    assert (await _upload(api, case["case_id"], name="fake.pdf", content=b"not a pdf")).status_code == 409
    assert (await _upload(api, case["case_id"], user="viewer")).status_code == 404
    assert (await _upload(api, case["case_id"], user="carol")).status_code == 403   # owner, not a reviewer


async def test_the_evidence_pack_tells_the_whole_story(api):
    case = await _case(api)
    await _upload(api, case["case_id"])
    for g in case["groups"]:
        await api.post(f"/api/cases/{case['case_id']}/decisions", headers=api.as_user("alice"),
                       json={"group_id": g["group_id"], "action": "approve",
                             "idempotency_key": f"{case['case_id']}-{g['group_id']}"})
    await api.post(f"/api/cases/{case['case_id']}/publish", headers=api.as_user("bob"),
                   json={"idempotency_key": "release-for-pack"})
    res = await api.get(f"/api/cases/{case['case_id']}/evidence-pack", headers=api.as_user("bob"))
    assert res.status_code == 200 and res.content.startswith(b"%PDF")
    text = "\n".join(p.extract_text() for p in PdfReader(io.BytesIO(res.content)).pages)
    for expected in ("Evidence pack", "Findings and decisions", "Released by bob", "Data access",
                     "gl.balances", "Data protection in force", "support.pdf", "alice"):
        assert expected in text, expected
    assert (await api.get(f"/api/cases/{case['case_id']}/evidence-pack", headers=api.as_user("viewer"))).status_code == 404
