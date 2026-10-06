"""Stub banking systems beyond finance: payment exceptions, the team's own
risk scoring service, and reference data (FX rates). Deterministic, so tests
and demos are stable. In the office each is an MCP server on the real system
(see config/agent-one-finance/connectors.office.example.yaml)."""

import zlib

from mcp.server.mcpserver import MCPServer

from agent_one_finance.stub_connectors.finance import _rng

# ---------- reference data ----------

# Value of one unit of each currency in GBP, per date. ZAR is deliberately
# absent: a conversion step must flag it, never assume a rate.
_FX = {"GBP": 1.0, "USD": 0.79, "EUR": 0.86, "JPY": 0.0053, "CHF": 0.90, "SGD": 0.59}


def fx_rates(date: str) -> dict:
    """End-of-day FX rates for a date: value of one unit of each currency in GBP."""
    r = _rng("fx", date)
    return {"rows": [{"currency": c, "rate": round(v * (1 + r.uniform(-0.004, 0.004)), 6) if c != "GBP" else 1.0,
                      "date": date} for c, v in _FX.items()]}


def build_refdata() -> MCPServer:
    server = MCPServer(name="refdata", instructions="Reference data: FX rates (stub).")
    server.add_tool(fx_rates, name="fx_rates", description=fx_rates.__doc__)
    return server


# ---------- payments operations ----------

REASONS = {"AC04": "Closed account", "AM04": "Insufficient funds", "BE04": "Missing creditor address",
           "RC01": "Bank identifier incorrect", "MS03": "Reason not specified"}
BANKS = ["DEUTDEFF", "BNPAFRPP", "CHASUS33", "HSBCHKHH", "SCBLSGSG", "NEDSZAJJ"]
CCY = ["GBP", "USD", "EUR", "EUR", "USD", "JPY", "CHF", "ZAR"]


def _exceptions(entity: str, date: str) -> list[dict]:
    r = _rng("payments", entity, date)
    rows = []
    for i in range(1, 15):
        reason = r.choice(list(REASONS))
        ccy = r.choice(CCY)
        amount = round(r.uniform(150, 2_500_000) / (150 if ccy == "JPY" else 1), 2) * (150 if ccy == "JPY" else 1)
        hour = r.randint(0, 17)
        rows.append({"exception_id": f"PX-{entity}-{date.replace('-', '')}-{i:02d}",
                     "payment_ref": f"PAY{zlib.crc32(f'{entity}|{date}|{i}'.encode()) % 10**8:08d}",
                     "entity": entity, "received_at": f"{date}T{hour:02d}:{r.randint(0, 59):02d}:00",
                     "reason_code": reason, "reason": REASONS[reason], "currency": ccy, "amount": round(amount, 2),
                     "beneficiary": r.choice(["Acme Ltd", "Northwind GmbH", "Blue Harbor Pte", "Kestrel SA", "J. Patel"]),
                     "beneficiary_bank_bic": r.choice(BANKS), "channel": r.choice(["SWIFT", "SEPA", "FPS"]),
                     "is_test": False})
    # the same payment raised twice by two channels, and a test payment from the morning checks
    dup = dict(rows[2])
    dup["exception_id"] = dup["exception_id"][:-2] + "90"
    rows.append(dup)
    rows.append({**rows[0], "exception_id": rows[0]["exception_id"][:-2] + "99", "payment_ref": "TEST0001",
                 "amount": 1.0, "currency": "GBP", "is_test": True, "beneficiary": "Ops test"})
    return rows


def exceptions(entity: str, date: str) -> dict:
    """Payment exceptions (returns, rejects, repairs) for an entity and date."""
    return {"rows": _exceptions(entity, date)}


def message_trail(entity: str, date: str, reason_code: str | None = None) -> dict:
    """SWIFT/ISO 20022 messages for the day's exceptions (pacs.002, pacs.004, camt.029), optionally for one reason."""
    rows = []
    for x in _exceptions(entity, date):
        if reason_code and x["reason_code"] != reason_code:
            continue
        rows.append({"payment_ref": x["payment_ref"], "message": "pacs.004" if x["reason_code"] in ("AC04", "AM04") else "pacs.002",
                     "status": "RJCT" if x["reason_code"] != "AC04" else "RTRN", "reason_code": x["reason_code"],
                     "amount": x["amount"], "currency": x["currency"], "counterparty_bic": x["beneficiary_bank_bic"]})
    return {"rows": rows}


def risk_score(entity: str, date: str, items: list[dict]) -> dict:
    """The payments team's own risk scoring service: a 0–100 score and its reasons per item.
    (In the office, the team's model behind its own API.)"""
    out = []
    for it in items:
        score, why = 10, []
        amt = float(it.get("amount_gbp") or 0)
        if amt > 1_000_000:
            score += 40
            why.append("over 1m GBP")
        elif amt > 100_000:
            score += 20
            why.append("over 100k GBP")
        if it.get("beneficiary_bank_bic") == "NEDSZAJJ":
            score += 25
            why.append("correspondent on enhanced monitoring")
        if it.get("reason_code") in ("RC01", "MS03"):
            score += 15
            why.append("unclear reject reason")
        out.append({"item_id": it["item_id"], "risk_score": min(score, 100), "risk_reasons": why})
    return {"rows": out}


def build_payments() -> MCPServer:
    server = MCPServer(name="payments", instructions="Payments operations (stub).")
    server.add_tool(exceptions, name="exceptions", description=exceptions.__doc__)
    server.add_tool(message_trail, name="message_trail", description=message_trail.__doc__)
    server.add_tool(risk_score, name="risk_score", description=risk_score.__doc__)
    return server


# ---------- ledger: periods, chart of accounts, journals ----------

POSTED: list[dict] = []          # what the stub ledger received, for tests and demos


def period_status(entity: str, period: str) -> dict:
    """Whether the accounting period is open, closed or locked for an entity."""
    status = "closed" if period < "2026-09" else "open"
    return {"rows": [{"entity": entity, "period": period, "status": status}]}


def chart_of_accounts(entity: str) -> dict:
    """The entity's chart of accounts: postable accounts."""
    return {"rows": [{"account": a, "name": n} for a, n in [
        ("2100", "Accruals"), ("2150", "Goods received not invoiced"), ("6100", "Professional fees"),
        ("6200", "IT services"), ("6300", "Facilities"), ("1400", "Prepayments"), ("7100", "FX revaluation")]]}


def validate_journal(entity: str, period: str, journal_id: str, lines: list[dict]) -> dict:
    """The ledger's own check of a journal before posting (a dry run): balanced, accounts, period."""
    errors = []
    accounts = {r["account"] for r in chart_of_accounts(entity)["rows"]}
    dr = round(sum(x["amount"] for x in lines if x["side"] == "debit"), 2)
    cr = round(sum(x["amount"] for x in lines if x["side"] == "credit"), 2)
    if dr != cr:
        errors.append("unbalanced")
    errors += [f"account {x['account']} not postable" for x in lines if x["account"] not in accounts]
    if period_status(entity, period)["rows"][0]["status"] != "open":
        errors.append(f"period {period} is not open")
    return {"ok": not errors, "errors": errors}


def post_journal(entity: str, period: str, journal_id: str, lines: list[dict], idempotency_key: str | None = None) -> dict:
    """Post a journal to the ledger. A repeat with the same idempotency key returns the first reference."""
    for p in POSTED:
        if idempotency_key and p["idempotency_key"] == idempotency_key:
            return {"reference": p["reference"], "posted": True, "replayed": True}
    ref = f"GL-{zlib.crc32(f'{entity}|{journal_id}'.encode()) % 10**7:07d}"
    POSTED.append({"entity": entity, "period": period, "journal_id": journal_id, "lines": lines,
                   "reference": ref, "idempotency_key": idempotency_key})
    return {"reference": ref, "posted": True}


def grni(entity: str, period: str) -> dict:
    """Goods received not invoiced at period end, per purchase order line."""
    r = _rng("grni", entity, period)
    return {"rows": [{"po_line": f"PO{4100 + i}-1", "supplier": r.choice(["Acme Ltd", "Northwind GmbH", "Kestrel SA"]),
                      "account": r.choice(["6100", "6200", "6300"]), "cost_centre": f"CC{r.randint(100, 140)}",
                      "received_value": round(r.uniform(2_000, 180_000), 2), "invoiced_value": 0.0,
                      "received_on": f"{period}-{r.randint(5, 28):02d}"} for i in range(1, 9)]}


def build_ledger() -> MCPServer:
    server = MCPServer(name="ledger", instructions="General ledger (stub).")
    for fn, name in ((period_status, "period_status"), (chart_of_accounts, "chart_of_accounts"),
                     (validate_journal, "validate_journal"), (post_journal, "post_journal"), (grni, "grni")):
        server.add_tool(fn, name=name, description=fn.__doc__)
    return server


# ---------- delegated authority ----------

def delegated_authority(entity: str) -> dict:
    """The entity's delegated authority matrix: who may approve how much."""
    return {"rows": [
        {"label": "up to 50k", "min_amount": 0, "max_amount": 50_000, "roles": "FIN_PREPARER,FIN_REVIEWER", "approvals": 1, "lane": "standard"},
        {"label": "50k to 250k", "min_amount": 50_000, "max_amount": 250_000, "roles": "FIN_REVIEWER", "approvals": 1, "lane": "standard"},
        {"label": "over 250k", "min_amount": 250_000, "max_amount": None, "roles": "FIN_REVIEWER", "approvals": 2,
         "lane": "enhanced", "bulk": False}]}


def build_authority() -> MCPServer:
    server = MCPServer(name="authority", instructions="Delegated authority (stub).")
    server.add_tool(delegated_authority, name="delegated_authority", description=delegated_authority.__doc__)
    return server


# ---------- client channel ----------

SENT: list[dict] = []


def send_message(to: str, subject: str, body: str, case_ref: str, step: str | None = None,
                 idempotency_key: str | None = None) -> dict:
    """Send a message to a client or counterparty through the bank's channel. Same key, same message."""
    for m in SENT:
        if idempotency_key and m["idempotency_key"] == idempotency_key:
            return {"message_id": m["message_id"], "replayed": True}
    mid = f"MSG-{zlib.crc32(f'{case_ref}|{to}|{subject}'.encode()) % 10**7:07d}"
    SENT.append({"to": to, "subject": subject, "body": body, "case_ref": case_ref, "message_id": mid,
                 "idempotency_key": idempotency_key})
    return {"message_id": mid}


def build_channel() -> MCPServer:
    server = MCPServer(name="channel", instructions="Client and counterparty messaging (stub).")
    server.add_tool(send_message, name="send_message", description=send_message.__doc__)
    return server


# ---------- client service: complaints and account events ----------

def complaints(entity: str, date: str) -> dict:
    """Complaints received for an entity on a date."""
    r = _rng("complaints", entity, date)
    topics = [("fees", "Charged an unarranged overdraft fee"), ("payments", "International payment arrived late"),
              ("fees", "Card fee charged twice"), ("service", "Branch did not call back")]
    rows = []
    for i in range(1, 6):
        topic, text = r.choice(topics)
        rows.append({"complaint_id": f"CMP-{entity}-{date.replace('-', '')}-{i}", "client": r.choice(["J. Patel", "Acme Ltd", "M. Okafor", "Blue Harbor Pte"]),
                     "account": f"ACC{r.randint(1000, 1099)}", "topic": topic, "summary": text,
                     "received_at": f"{date}T{r.randint(8, 17):02d}:00:00", "claimed": round(r.uniform(10, 900), 2),
                     "fee_charged": round(r.choice([25.0, 30.0, 35.0]), 2), "fee_tariff": 25.0})
    return {"rows": rows}


def account_events(entity: str, date: str) -> dict:
    """Account events around a date (fees, payments, calls) for complaint timelines."""
    r = _rng("acct-events", entity, date)
    return {"rows": [{"at": f"{date}T{h:02d}:{r.randint(0, 59):02d}:00", "account": f"ACC{r.randint(1000, 1099)}",
                      "event": r.choice(["fee charged", "payment sent", "call logged", "statement issued"]),
                      "amount": round(r.uniform(5, 500), 2)} for h in range(7, 19, 2)]}


def watch_list() -> dict:
    """The team's internal watch list (names supplied by the control function)."""
    return {"rows": [{"id": "WL-1", "name": "Kestrel S.A."}, {"id": "WL-2", "name": "Northwind Holdings GmbH"},
                     {"id": "WL-3", "name": "Blue Harbour Pte Ltd"}]}


def build_client() -> MCPServer:
    server = MCPServer(name="client", instructions="Client service: complaints, account events, watch list (stub).")
    for fn, name in ((complaints, "complaints"), (account_events, "account_events"), (watch_list, "watch_list")):
        server.add_tool(fn, name=name, description=fn.__doc__)
    return server


# ---------- procurement: purchase orders, goods receipts, invoices ----------

def _po_lines(entity: str, period: str) -> list[dict]:
    r = _rng("po", entity, period)
    return [{"po_line": f"PO{5200 + i}-1", "supplier": r.choice(["Acme Ltd", "Northwind GmbH", "Kestrel SA"]),
             "amount": round(r.uniform(1_000, 60_000), 2)} for i in range(1, 11)]


def purchase_orders(entity: str, period: str) -> dict:
    """Purchase order lines for a period."""
    return {"rows": _po_lines(entity, period)}


def goods_receipts(entity: str, period: str) -> dict:
    """Goods receipts against purchase order lines (sometimes in two deliveries)."""
    r = _rng("gr", entity, period)
    rows = []
    for po in _po_lines(entity, period):
        roll = r.random()
        if roll < 0.1:
            continue                                   # nothing received yet
        if roll < 0.3:
            half = round(po["amount"] / 2, 2)
            rows += [{"po_line": po["po_line"], "amount": half}, {"po_line": po["po_line"], "amount": round(po["amount"] - half, 2)}]
        else:
            rows.append({"po_line": po["po_line"], "amount": po["amount"]})
    return {"rows": rows}


def invoices(entity: str, period: str) -> dict:
    """Supplier invoices against purchase order lines."""
    r = _rng("inv", entity, period)
    rows = []
    for po in _po_lines(entity, period):
        roll = r.random()
        if roll < 0.15:
            continue
        amt = po["amount"] if roll > 0.3 else round(po["amount"] * 1.05, 2)    # price variance
        rows.append({"po_line": po["po_line"], "amount": amt, "invoice": f"INV-{po['po_line']}"})
    return {"rows": rows}


def build_procurement() -> MCPServer:
    server = MCPServer(name="procurement", instructions="Procurement (stub).")
    for fn, name in ((purchase_orders, "purchase_orders"), (goods_receipts, "goods_receipts"), (invoices, "invoices")):
        server.add_tool(fn, name=name, description=fn.__doc__)
    return server


# ---------- controls testing ----------

def control_evidence(entity: str, date: str, item_ref: str) -> dict:
    """Test attributes for one sampled item: was each control step performed and evidenced?"""
    r = _rng("ctl", entity, date, item_ref)
    return {"rows": [{"attribute": a, "item_ref": item_ref, "performed": r.random() > 0.15,
                      "evidence": r.choice(["ticket", "email approval", "system log"])}
                     for a in ("four-eyes approval", "within limit", "timely")]}


def build_controls() -> MCPServer:
    server = MCPServer(name="controls", instructions="Controls testing evidence (stub).")
    server.add_tool(control_evidence, name="evidence", description=control_evidence.__doc__)
    return server
