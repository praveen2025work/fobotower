"""Sample documents for the documents service (dev and tests).

Writes, per entity, a management report workbook for 2026-09 built from the
stub general ledger with a few deliberate differences — the cases a report
validation has to explain — and a short PDF of the business's commentary.

    python scripts/make_aof_documents.py   # -> seed_data/aof_documents/<entity>/
"""

from pathlib import Path

from openpyxl import Workbook

from agent_one_finance.stub_connectors.finance import balances

OUT = Path(__file__).resolve().parents[1] / "seed_data" / "aof_documents"
PERIOD = "2026-09"


def workbook(entity: str) -> Path:
    rows = balances(entity, PERIOD)["rows"]
    wb = Workbook()
    ws = wb.active
    ws.title = "P&L"
    ws.append(["account", "account_name", "cost_centre", "actual"])
    for r in rows:
        actual = r["actual"]
        if (r["account"], r["cost_centre"]) == ("6300", "CC10"):
            actual = round(actual + 25_000, 2)        # late IT accrual in the report only
        elif (r["account"], r["cost_centre"]) == ("4000", "CC20"):
            actual = round(actual - 3.20, 2)          # rounding in the report
        elif (r["account"], r["cost_centre"]) == ("7200", "CC20"):
            continue                                   # line dropped from the report
        ws.append([r["account"], r["account_name"], r["cost_centre"], actual])
    ws.append(["6900", "Restructuring", "CC10", 40_000.00])   # in the report, not in the ledger
    path = OUT / entity / f"mgmt-report-{PERIOD}.xlsx"
    path.parent.mkdir(parents=True, exist_ok=True)
    wb.save(path)
    return path


def commentary(entity: str) -> Path:
    from reportlab.lib.pagesizes import A4
    from reportlab.pdfgen import canvas

    path = OUT / entity / f"mgmt-commentary-{PERIOD}.pdf"
    c = canvas.Canvas(str(path), pagesize=A4)
    lines = [
        f"{entity} management commentary, {PERIOD}",
        "",
        "IT services: includes a 25,000.00 accrual for the data-centre migration,",
        "booked in the report ahead of the ledger posting in October.",
        "Restructuring: 40,000.00 provision agreed by the business, ledger posting pending.",
        "Interest CC20: reported within CC10 this month.",
    ]
    y = 800
    for line in lines:
        c.drawString(56, y, line)
        y -= 16
    c.save()
    return path


if __name__ == "__main__":
    for e in ("UK01", "US01"):
        print(workbook(e))
        print(commentary(e))
