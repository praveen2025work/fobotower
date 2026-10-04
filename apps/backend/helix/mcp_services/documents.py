"""Documents — a Helix-provided MCP service: read PDFs and Excel workbooks,
write PDF reports.

Unlike the stubs, this is a real service: it reads and writes files. It is
onboarded like any other connector (config/helix/connectors.yaml), so every
call goes through the gateway: the allow-list, the caller's data scope, the
audit row and the trace. `render_pdf_report` is a write tool, so only a
capability's `publish` step can call it, after a second person releases the
case; the model never can.

Documents to read live under one folder per data-scope value (an entity, a
book): <HELIX_DOCUMENTS_DIR>/<scope>/<name>. Reports Helix writes are kept in
the shared database (helix_document) so every API instance can serve them,
or with HELIX_REPORTS_STORE=fs under <HELIX_REPORTS_DIR>/<scope>/.

In the office, point both at the team share or swap the folder for the
document store's API; the tools and their arguments stay the same.

Serve over HTTP:  python -m helix.mcp_services.documents --port 9201
"""

import argparse
import datetime as dt
import hashlib
import io
import re
from pathlib import Path
from typing import Any
from xml.sax.saxutils import escape

from mcp.server.mcpserver import MCPServer
from mcp.server.mcpserver.exceptions import ToolError

from helix.config import settings

_NAME = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._ -]{0,127}$")
MAX_PAGES = 200
MAX_ROWS = 20_000


class DocumentError(ToolError):
    """A refusal the caller should see (bad name, missing file), not a crash."""


def _safe(part: str, what: str) -> str:
    if not isinstance(part, str) or not _NAME.match(part) or ".." in part:
        raise DocumentError(f"invalid {what}: {part!r}")
    return part


def _inbox(scope: str) -> Path:
    return settings().documents_dir / _safe(scope, "scope")


def _outbox(scope: str) -> Path:
    return settings().reports_dir / _safe(scope, "scope")


def _file(scope: str, name: str) -> Path:
    path = _inbox(scope) / _safe(name, "document name")
    if not path.is_file():
        raise DocumentError(f"no document {name!r} for {scope}")
    return path


def _cell(v: Any) -> Any:
    return v.isoformat() if isinstance(v, (dt.datetime, dt.date, dt.time)) else v


def _when(v: Any) -> Any:
    """ISO timestamps as '04 Oct 2026 10:03 UTC'; anything else as given."""
    try:
        t = dt.datetime.fromisoformat(str(v))
    except ValueError:
        return v
    return t.astimezone(dt.timezone.utc).strftime("%d %b %Y %H:%M UTC") if t.tzinfo else t.strftime("%d %b %Y %H:%M")


# ---------- tools ----------

def list_documents(entity: str) -> dict:
    """Documents available to read for one data scope (PDF and Excel)."""
    folder = _inbox(entity)
    rows = []
    if folder.is_dir():
        for p in sorted(folder.iterdir()):
            if p.is_file() and p.suffix.lower() in (".pdf", ".xlsx", ".xlsm"):
                st = p.stat()
                rows.append({"name": p.name, "kind": p.suffix.lower().lstrip("."),
                             "bytes": st.st_size,
                             "modified": dt.datetime.fromtimestamp(st.st_mtime, dt.timezone.utc).isoformat()})
    return {"rows": rows}


def read_pdf(entity: str, name: str, max_pages: int = 50) -> dict:
    """Text of a PDF, page by page."""
    from pypdf import PdfReader

    reader = PdfReader(str(_file(entity, name)))
    limit = max(1, min(int(max_pages), MAX_PAGES))
    rows = [{"page": i + 1, "text": (page.extract_text() or "").strip()}
            for i, page in enumerate(reader.pages[:limit])]
    return {"document": name, "pages": len(reader.pages), "truncated": len(reader.pages) > limit,
            "rows": rows}


def read_workbook(entity: str, name: str, sheet: str | None = None, header_row: int = 1,
                  max_rows: int = 5000) -> dict:
    """Rows of one sheet of an Excel workbook, keyed by the header row."""
    from openpyxl import load_workbook

    wb = load_workbook(str(_file(entity, name)), read_only=True, data_only=True)
    try:
        if sheet is not None and sheet not in wb.sheetnames:
            raise DocumentError(f"no sheet {sheet!r} in {name} (sheets: {', '.join(wb.sheetnames)})")
        ws = wb[sheet] if sheet else wb.worksheets[0]
        limit = max(1, min(int(max_rows), MAX_ROWS))
        columns: list[str] = []
        rows: list[dict] = []
        truncated = False
        for i, values in enumerate(ws.iter_rows(values_only=True), start=1):
            if i < header_row:
                continue
            if i == header_row:
                columns = [str(v).strip() if v is not None else f"col{j + 1}" for j, v in enumerate(values)]
                continue
            if all(v is None for v in values):
                continue
            if len(rows) >= limit:
                truncated = True
                break
            rows.append({c: _cell(v) for c, v in zip(columns, values)})
        return {"document": name, "sheet": ws.title, "sheets": wb.sheetnames, "columns": columns,
                "truncated": truncated, "rows": rows}
    finally:
        wb.close()


async def render_pdf_report(entity: str, name: str, title: str, subtitle: str = "",
                            sections: list[dict] | None = None, sign_off: list[dict] | None = None,
                            idempotency_key: str | None = None) -> dict:
    """Write a PDF report: a title, sections (heading, body, optional table of
    columns and rows) and a sign-off block. The same name replaces the report,
    so a repeated write is the same write."""
    from reportlab.lib import colors
    from reportlab.lib.pagesizes import A4, landscape
    from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
    from reportlab.lib.units import mm
    from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle

    file_name = _safe(name, "report name")
    if not file_name.lower().endswith(".pdf"):
        file_name += ".pdf"
    navy, cyan, grey = colors.HexColor("#00395D"), colors.HexColor("#00AEEF"), colors.HexColor("#61778C")
    base = getSampleStyleSheet()
    h1 = ParagraphStyle("h1", parent=base["Title"], textColor=navy, alignment=0, fontSize=18, spaceAfter=2)
    sub = ParagraphStyle("sub", parent=base["Normal"], textColor=grey, fontSize=9, spaceAfter=10)
    h2 = ParagraphStyle("h2", parent=base["Heading2"], textColor=navy, fontSize=12, spaceBefore=10)
    body = ParagraphStyle("body", parent=base["Normal"], fontSize=9.5, leading=13)
    cell = ParagraphStyle("cell", parent=base["Normal"], fontSize=8, leading=10)

    def text(v: Any) -> str:
        if isinstance(v, float):
            return f"{v:,.2f}"
        return escape("" if v is None else str(v))

    story: list = [Paragraph(escape(title), h1)]
    stamp = dt.datetime.now(dt.timezone.utc).strftime("%d %b %Y %H:%M UTC")
    story.append(Paragraph(f"{escape(subtitle or entity)} · generated {stamp}", sub))
    for s in sections or []:
        story.append(Paragraph(escape(str(s.get("heading", ""))), h2))
        if s.get("body"):
            story.append(Paragraph(escape(str(s["body"])).replace("\n", "<br/>"), body))
        cols, rows = s.get("columns") or [], s.get("rows") or []
        if cols and rows:
            data = [[Paragraph(f"<b>{text(c)}</b>", cell) for c in cols]]
            data += [[Paragraph(text(r.get(c) if isinstance(r, dict) else None), cell) for c in cols]
                     for r in rows[:500]]
            t = Table(data, repeatRows=1, hAlign="LEFT")
            t.setStyle(TableStyle([
                ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#E6F6FD")),
                ("LINEBELOW", (0, 0), (-1, 0), 0.8, cyan),
                ("GRID", (0, 1), (-1, -1), 0.25, colors.HexColor("#D8E2EB")),
                ("VALIGN", (0, 0), (-1, -1), "TOP"),
            ]))
            story += [Spacer(1, 4), t]
    if sign_off:
        story.append(Paragraph("Sign-off", h2))
        data = [[Paragraph("<b>Step</b>", cell), Paragraph("<b>By</b>", cell), Paragraph("<b>When</b>", cell)]]
        data += [[Paragraph(text(r.get("step")), cell), Paragraph(text(r.get("by")), cell),
                  Paragraph(text(_when(r.get("at"))), cell)] for r in sign_off]
        t = Table(data, hAlign="LEFT", colWidths=[40 * mm, 70 * mm, 60 * mm])
        t.setStyle(TableStyle([("GRID", (0, 0), (-1, -1), 0.25, colors.HexColor("#D8E2EB")),
                               ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#E6F6FD"))]))
        story.append(t)

    wide = any(len(s.get("columns") or []) > 6 for s in sections or [])
    buf = io.BytesIO()

    def footer(canvas, doc):
        canvas.saveState()
        canvas.setFillColor(grey)
        canvas.setFont("Helvetica", 7)
        canvas.drawString(doc.leftMargin, 8 * mm, f"Helix · {title} · page {doc.page}")
        canvas.restoreState()

    doc = SimpleDocTemplate(buf, pagesize=landscape(A4) if wide else A4, title=title, author="Helix",
                            leftMargin=15 * mm, rightMargin=15 * mm, topMargin=15 * mm, bottomMargin=15 * mm)
    doc.build(story, onFirstPage=footer, onLaterPages=footer)
    data = buf.getvalue()
    digest = hashlib.sha256(data).hexdigest()
    await save_report(entity, file_name, data, "application/pdf", digest)
    return {"document": file_name, "scope": entity, "pages": doc.page, "bytes": len(data),
            "sha256": digest, "published": True}


def build_documents() -> MCPServer:
    server = MCPServer(name="documents",
                       instructions="Read PDF and Excel documents; write PDF reports (publish only).")
    for fn in (list_documents, read_pdf, read_workbook, render_pdf_report):
        server.add_tool(fn, name=fn.__name__, description=fn.__doc__)
    return server


# ---------- the report store ----------

async def save_report(scope: str, name: str, data: bytes, content_type: str, digest: str) -> None:
    if settings().reports_store == "fs":
        folder = _outbox(scope)
        folder.mkdir(parents=True, exist_ok=True)
        (folder / _safe(name, "report name")).write_bytes(data)
        return
    from helix.db import get_session
    from helix.models import Document

    async with get_session() as s:
        await s.merge(Document(scope=_safe(scope, "scope"), name=_safe(name, "report name"),
                               content=data, content_type=content_type, sha256=digest))
        await s.commit()


async def load_report(scope: str, name: str) -> tuple[bytes, str]:
    """(content, content type) of a written report (the console's download)."""
    if settings().reports_store == "fs":
        path = _outbox(scope) / _safe(name, "report name")
        if not path.is_file():
            raise DocumentError(f"no report {name!r} for {scope}")
        return path.read_bytes(), "application/pdf" if name.lower().endswith(".pdf") else "application/octet-stream"
    from helix.db import get_session
    from helix.models import Document

    async with get_session() as s:
        row = await s.get(Document, (scope, name))
    if row is None:
        raise DocumentError(f"no report {name!r} for {scope}")
    return row.content, row.content_type


def main() -> None:
    import uvicorn

    p = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    p.add_argument("--port", type=int, default=9201)
    a = p.parse_args()
    app = build_documents().streamable_http_app(streamable_http_path="/mcp", stateless_http=True,
                                                json_response=True)
    uvicorn.run(app, host="127.0.0.1", port=a.port)


if __name__ == "__main__":
    main()
