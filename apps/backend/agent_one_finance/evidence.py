"""Evidence in a task, and the task's evidence pack.

Upload: a reviewer attaches the business's support (a PDF or a workbook) to
the task. It is kept in the shared document store under the task's data
scope, so the agent's document tools — and the model, through the
gateway — can read it like any other document. Who uploaded what, when, and
its checksum are recorded.

Evidence pack: one PDF an auditor can take away — the task, the configuration
it ran on, every finding and who decided it, the release and what was written,
every data access (allowed or refused), the data protection in force, and the
evidence uploaded. Built from the records on demand; nothing is retyped.
"""

import hashlib
import re

from sqlalchemy import select

from agent_one_finance import runner
from agent_one_finance.tasks import TaskError, task_detail, may_see_task
from agent_one_finance.db import get_session
from agent_one_finance.entitlement import Caller
from agent_one_finance.governance import fields_for
from agent_one_finance.models import Task, Document, PublishApproval

MAX_BYTES = 10 * 1024 * 1024
KINDS = {".pdf": ("application/pdf", b"%PDF"),
         ".xlsx": ("application/vnd.openxmlformats-officedocument.spreadsheetml.sheet", b"PK"),
         ".xlsm": ("application/vnd.ms-excel.sheet.macroEnabled.12", b"PK")}


def _clean(filename: str) -> str:
    base = re.sub(r"[^A-Za-z0-9._ -]", "_", filename.rsplit("/", 1)[-1].rsplit("\\", 1)[-1]).strip(" .")
    return base[:120] or "evidence"


async def _task(task_id: str, caller: Caller):
    async with get_session() as s:
        task = await s.get(Task, task_id)
    if task is None:
        raise LookupError(task_id)
    m = await runner.pinned(task)
    if not may_see_task(caller, m, task.task_key):
        raise LookupError(task_id)
    return task, m


def _scope_of(task: Task) -> str:
    """The task's data scope value its documents are filed under."""
    values = list((task.scope or {}).values()) or list(task.task_key.values())
    return str(values[0])


async def upload(task_id: str, filename: str, content: bytes, note: str | None, caller: Caller) -> dict:
    task, m = await _task(task_id, caller)
    if not (caller.has_any_role(m.review.roles) or caller.user_id == task.opened_by):
        raise PermissionError(f"{caller.user_id} may not add evidence to this task")
    return await store(task, filename, content, note, caller.user_id)


async def store(task: Task, filename: str, content: bytes, note: str | None, uploaded_by: str) -> dict:
    """Keep a file as the task's evidence (checked: type, size, real content).
    Who may add it is the caller's to check — a reviewer, or someone answering
    a question about the task (asks.answer)."""
    name = _clean(filename)
    ext = "." + name.rsplit(".", 1)[-1].lower() if "." in name else ""
    if ext not in KINDS:
        raise TaskError(f"evidence must be one of: {', '.join(KINDS)}")
    if len(content) > MAX_BYTES:
        raise TaskError(f"evidence is at most {MAX_BYTES // (1024 * 1024)} MB")
    content_type, magic = KINDS[ext]
    if not content.startswith(magic):
        raise TaskError(f"{name} is not a real {ext} file")
    stored = f"{task.task_id}--{name}"
    digest = hashlib.sha256(content).hexdigest()
    async with get_session() as s:
        await s.merge(Document(scope=_scope_of(task), name=stored, content=content, content_type=content_type,
                               sha256=digest, kind="evidence", task_id=task.task_id,
                               uploaded_by=uploaded_by, note=(note or "").strip() or None))
        await s.commit()
    return {"name": stored, "sha256": digest, "bytes": len(content)}


async def for_task(task_id: str) -> list[dict]:
    async with get_session() as s:
        rows = (await s.execute(select(Document).where(
            Document.task_id == task_id, Document.kind == "evidence").order_by(Document.created_at))).scalars().all()
    return [{"name": d.name, "scope": d.scope, "bytes": len(d.content), "sha256": d.sha256,
             "uploaded_by": d.uploaded_by, "note": d.note, "uploaded_at": d.created_at,
             "url": f"/api/tasks/{task_id}/evidence/{d.name}"} for d in rows]


async def download(task_id: str, name: str, caller: Caller) -> tuple[bytes, str]:
    await _task(task_id, caller)
    async with get_session() as s:
        d = (await s.execute(select(Document).where(
            Document.task_id == task_id, Document.kind == "evidence", Document.name == name))).scalar_one_or_none()
    if d is None:
        raise LookupError(f"{task_id}/{name}")
    return d.content, d.content_type


# ---------- the evidence pack ----------

def _fmt(v) -> str:
    if v is None:
        return ""
    return v.isoformat() if hasattr(v, "isoformat") else str(v)


async def pack(task_id: str, caller: Caller) -> tuple[bytes, str]:
    """(PDF, file name) of the task's evidence pack."""
    from agent_one_finance.mcp_services.documents import build_pdf

    task, m = await _task(task_id, caller)
    d = await task_detail(task_id, caller)
    async with get_session() as s:
        release = await s.get(PublishApproval, task_id)
    mask, pseudo = fields_for(m.tools_used())
    sections = [
        {"heading": "Task",
         "columns": ["field", "value"],
         "rows": [{"field": k, "value": v} for k, v in [
             ("agent", f"{m.name} ({m.id}) v{task.manifest_version}"),
             ("team group", f"{task.team_group} v{task.team_group_version}" if task.team_group else "—"),
             ("task", task.task_id), ("subject", task.subject),
             *[(k, v) for k, v in task.task_key.items()],
             ("opened", f"{_fmt(task.opened_at)} by {task.opened_by}"),
             ("status", f"{task.status} / {task.outcome or '—'}"),
             ("attempt", f"{task.attempt or 1}" + (f" (re-run of {task.rerun_of})" if task.rerun_of else "")),
             ("legal hold", task.legal_hold_reason or "no"),
             ("trace", task.trace_id or "—"),
             ("headline", (task.draft or {}).get("headline", ""))]]},
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
                  f"Pseudonymized for the model (per-task tokens): {', '.join(sorted(pseudo)) or 'none'}.")},
        {"heading": "Evidence uploaded",
         "columns": ["name", "by", "when", "sha256"],
         "rows": [{"name": e["name"], "by": e["uploaded_by"], "when": _fmt(e["uploaded_at"]), "sha256": e["sha256"]}
                  for e in await for_task(task_id)],
         "body": "" if await for_task(task_id) else "None."},
    ]
    sign_off = [{"step": f"review: {x['group_id']}", "by": x["decided_by"], "at": _fmt(x["decided_at"])}
                for x in d["decisions"]]
    if release:
        sign_off.append({"step": "release", "by": release.approved_by, "at": _fmt(release.approved_at)})
    data, _ = build_pdf(f"Evidence pack — {m.task.label}", f"{task.subject} · {m.name}", sections, sign_off)
    return data, f"evidence-pack-{task.task_id}.pdf"
