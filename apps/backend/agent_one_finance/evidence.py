"""Evidence in a case, and the case's evidence pack.

Upload: a reviewer attaches the business's support (a PDF or a workbook) to
the case. It is kept in the shared document store under the case's data
scope, so the capability's document tools — and the model, through the
gateway — can read it like any other document. Who uploaded what, when, and
its checksum are recorded.

Evidence pack: one PDF an auditor can take away — the case, the configuration
it ran on, every finding and who decided it, the release and what was written,
every data access (allowed or refused), the data protection in force, and the
evidence uploaded. Built from the records on demand; nothing is retyped.
"""

import hashlib
import re

from sqlalchemy import select

from agent_one_finance import runner
from agent_one_finance.cases import CaseError, case_detail, may_see_case
from agent_one_finance.db import get_session
from agent_one_finance.entitlement import Caller
from agent_one_finance.governance import fields_for
from agent_one_finance.models import Case, Document, PublishApproval

MAX_BYTES = 10 * 1024 * 1024
KINDS = {".pdf": ("application/pdf", b"%PDF"),
         ".xlsx": ("application/vnd.openxmlformats-officedocument.spreadsheetml.sheet", b"PK"),
         ".xlsm": ("application/vnd.ms-excel.sheet.macroEnabled.12", b"PK")}


def _clean(filename: str) -> str:
    base = re.sub(r"[^A-Za-z0-9._ -]", "_", filename.rsplit("/", 1)[-1].rsplit("\\", 1)[-1]).strip(" .")
    return base[:120] or "evidence"


async def _case(case_id: str, caller: Caller):
    async with get_session() as s:
        case = await s.get(Case, case_id)
    if case is None:
        raise LookupError(case_id)
    m = await runner.pinned(case)
    if not may_see_case(caller, m, case.case_key):
        raise LookupError(case_id)
    return case, m


def _scope_of(case: Case) -> str:
    """The case's data scope value its documents are filed under."""
    values = list((case.scope or {}).values()) or list(case.case_key.values())
    return str(values[0])


async def upload(case_id: str, filename: str, content: bytes, note: str | None, caller: Caller) -> dict:
    case, m = await _case(case_id, caller)
    if not (caller.has_any_role(m.review.roles) or caller.user_id == case.opened_by):
        raise PermissionError(f"{caller.user_id} may not add evidence to this case")
    return await store(case, filename, content, note, caller.user_id)


async def store(case: Case, filename: str, content: bytes, note: str | None, uploaded_by: str) -> dict:
    """Keep a file as the case's evidence (checked: type, size, real content).
    Who may add it is the caller's to check — a reviewer, or someone answering
    a question about the case (asks.answer)."""
    name = _clean(filename)
    ext = "." + name.rsplit(".", 1)[-1].lower() if "." in name else ""
    if ext not in KINDS:
        raise CaseError(f"evidence must be one of: {', '.join(KINDS)}")
    if len(content) > MAX_BYTES:
        raise CaseError(f"evidence is at most {MAX_BYTES // (1024 * 1024)} MB")
    content_type, magic = KINDS[ext]
    if not content.startswith(magic):
        raise CaseError(f"{name} is not a real {ext} file")
    stored = f"{case.case_id}--{name}"
    digest = hashlib.sha256(content).hexdigest()
    async with get_session() as s:
        await s.merge(Document(scope=_scope_of(case), name=stored, content=content, content_type=content_type,
                               sha256=digest, kind="evidence", case_id=case.case_id,
                               uploaded_by=uploaded_by, note=(note or "").strip() or None))
        await s.commit()
    return {"name": stored, "sha256": digest, "bytes": len(content)}


async def for_case(case_id: str) -> list[dict]:
    async with get_session() as s:
        rows = (await s.execute(select(Document).where(
            Document.case_id == case_id, Document.kind == "evidence").order_by(Document.created_at))).scalars().all()
    return [{"name": d.name, "scope": d.scope, "bytes": len(d.content), "sha256": d.sha256,
             "uploaded_by": d.uploaded_by, "note": d.note, "uploaded_at": d.created_at,
             "url": f"/api/cases/{case_id}/evidence/{d.name}"} for d in rows]


async def download(case_id: str, name: str, caller: Caller) -> tuple[bytes, str]:
    await _case(case_id, caller)
    async with get_session() as s:
        d = (await s.execute(select(Document).where(
            Document.case_id == case_id, Document.kind == "evidence", Document.name == name))).scalar_one_or_none()
    if d is None:
        raise LookupError(f"{case_id}/{name}")
    return d.content, d.content_type


# ---------- the evidence pack ----------

def _fmt(v) -> str:
    if v is None:
        return ""
    return v.isoformat() if hasattr(v, "isoformat") else str(v)


async def pack(case_id: str, caller: Caller) -> tuple[bytes, str]:
    """(PDF, file name) of the case's evidence pack."""
    from agent_one_finance.mcp_services.documents import build_pdf

    case, m = await _case(case_id, caller)
    d = await case_detail(case_id, caller)
    async with get_session() as s:
        release = await s.get(PublishApproval, case_id)
    mask, pseudo = fields_for(m.tools_used())
    sections = [
        {"heading": "Case",
         "columns": ["field", "value"],
         "rows": [{"field": k, "value": v} for k, v in [
             ("capability", f"{m.name} ({m.id}) v{case.manifest_version}"),
             ("team group", f"{case.team_group} v{case.team_group_version}" if case.team_group else "—"),
             ("case", case.case_id), ("subject", case.subject),
             *[(k, v) for k, v in case.case_key.items()],
             ("opened", f"{_fmt(case.opened_at)} by {case.opened_by}"),
             ("status", f"{case.status} / {case.outcome or '—'}"),
             ("attempt", f"{case.attempt or 1}" + (f" (re-run of {case.rerun_of})" if case.rerun_of else "")),
             ("legal hold", case.legal_hold_reason or "no"),
             ("trace", case.trace_id or "—"),
             ("headline", (case.draft or {}).get("headline", ""))]]},
        {"heading": "How it ran",
         "body": (f"Steps: {' → '.join(m.steps)}. Paused for people before: {', '.join(m.pause_before)}. "
                  f"Reviewers: {', '.join(m.review.roles)}"
                  + (f"; write-back released by {', '.join(m.publish.approver_roles)} (four-eyes)" if m.publish else "")
                  + f". Comments required to: {', '.join(m.review.require_comment) or 'never'}.")},
        {"heading": "Findings and decisions",
         "columns": ["group", "finding", "by", "verdict", "decision", "decided by", "comment"],
         "rows": [{"group": g["label"],
                   "finding": (g["finding"] or {}).get("status", ""),
                   "by": (g["finding"] or {}).get("decided_by", ""),
                   "verdict": (g["finding"] or {}).get("verdict") or "",
                   "decision": (g["decision"] or {}).get("action", "pending"),
                   "decided by": (g["decision"] or {}).get("decided_by", ""),
                   "comment": ((g["decision"] or {}).get("comment") or (g["finding"] or {}).get("comment") or "")[:300]}
                  for g in d["groups"]]},
        {"heading": "Release and write-back",
         "body": (f"Released by {release.approved_by} at {_fmt(release.approved_at)}." if release
                  else "Not released (no write-back, or not yet)."),
         "columns": ["document", "sha256", "pages"] if d["documents"] else [],
         "rows": [{"document": x["name"], "sha256": x["sha256"], "pages": x["pages"]} for x in d["documents"]]},
        {"heading": f"Data access ({len(d['tool_calls'])} connector calls)",
         "columns": ["when", "tool", "by", "allowed", "rows", "note"],
         "rows": [{"when": _fmt(t["called_at"]), "tool": t["tool"], "by": t["requested_by"],
                   "allowed": "yes" if t["allowed"] else "REFUSED", "rows": t["row_count"],
                   "note": t["denied_reason"] or t["error"] or ""} for t in d["tool_calls"]]},
        {"heading": "Data protection in force",
         "body": (f"Masked (never shown to the model, traces or audit copies): {', '.join(sorted(mask)) or 'none'}. "
                  f"Pseudonymized for the model (per-case tokens): {', '.join(sorted(pseudo)) or 'none'}.")},
        {"heading": "Evidence uploaded",
         "columns": ["name", "by", "when", "sha256"],
         "rows": [{"name": e["name"], "by": e["uploaded_by"], "when": _fmt(e["uploaded_at"]), "sha256": e["sha256"]}
                  for e in await for_case(case_id)],
         "body": "" if await for_case(case_id) else "None."},
    ]
    sign_off = [{"step": f"review: {x['group_id']}", "by": x["decided_by"], "at": _fmt(x["decided_at"])}
                for x in d["decisions"]]
    if release:
        sign_off.append({"step": "release", "by": release.approved_by, "at": _fmt(release.approved_at)})
    data, _ = build_pdf(f"Evidence pack — {m.case.label}", f"{case.subject} · {m.name}", sections, sign_off)
    return data, f"evidence-pack-{case.case_id}.pdf"
