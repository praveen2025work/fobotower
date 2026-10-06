"""Stub banking systems beyond finance: payment exceptions, the team's own
risk scoring service, and reference data (FX rates). Deterministic, so tests
and demos are stable. In the office each is an MCP server on the real system
(see config/helix/connectors.office.example.yaml)."""

import zlib

from mcp.server.mcpserver import MCPServer

from helix.stub_connectors.finance import _rng

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
