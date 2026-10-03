"""Stand-in bank systems, as real MCP servers, for the skeleton and its tests.

In the office each of these is replaced by the real connector: change its
entry in config/helix/connectors.yaml from `transport: inproc` to
`transport: http` with the connector's URL. Nothing else changes.

Data is generated deterministically from the arguments, so every run of the
same case sees the same figures.

Serve one over HTTP, e.g. to try the http transport:
    python -m helix.stub_connectors.finance gl --port 9101
"""

import argparse
import random
import zlib

from mcp.server.mcpserver import MCPServer

ACCOUNTS = {
    "4000": "Revenue", "5000": "Cost of sales", "6100": "Salaries", "6200": "Travel",
    "6300": "IT services", "7100": "FX revaluation", "7200": "Interest",
}
COST_CENTRES = ["CC10", "CC20"]
COUNTERPARTIES = ["ACME BANK", "GLOBEX", "INITECH", "UMBRELLA", "STARK"]


def _rng(*parts: str) -> random.Random:
    return random.Random("|".join(parts))


def _budget(entity: str, period: str, account: str, cc: str) -> float:
    return round(_rng("budget", entity, period, account, cc).uniform(80_000, 900_000), 2)


def _actual(entity: str, period: str, account: str, cc: str) -> float:
    r = _rng("actual", entity, period, account, cc)
    drift = r.choice([0.01, -0.02, 0.03, 0.12, -0.18, 0.25])
    return round(_budget(entity, period, account, cc) * (1 + drift), 2)


# ---------- general ledger ----------

def balances(entity: str, period: str) -> dict:
    """Actual and budget per account and cost centre for one entity and period."""
    rows = [{"line_id": f"{entity}-{period}-{a}-{cc}", "account": a, "account_name": n,
             "cost_centre": cc, "actual": _actual(entity, period, a, cc),
             "budget": _budget(entity, period, a, cc)}
            for a, n in ACCOUNTS.items() for cc in COST_CENTRES]
    return {"rows": rows}


def journal_lines(entity: str, period: str, account: str) -> dict:
    """The largest journal lines posted to one account in the period."""
    r = _rng("journals", entity, period, account)
    rows = [{"journal_id": f"JE-{r.randint(10000, 99999)}", "account": account,
             "amount": round(r.uniform(5_000, 120_000), 2),
             "description": r.choice(["Accrual", "Reclass", "Vendor invoice",
                                      "Payroll run", "Reval adjustment"]),
             "posted_on": f"{period}-{r.randint(1, 28):02d}"} for _ in range(4)]
    return {"rows": rows}


def build_gl() -> MCPServer:
    server = MCPServer(name="gl", instructions="General ledger (stub): balances and journals.")
    server.add_tool(balances, name="balances", description=balances.__doc__)
    server.add_tool(journal_lines, name="journal_lines", description=journal_lines.__doc__)
    return server


# ---------- budget ----------

def plan_lines(entity: str, period: str, account: str) -> dict:
    """Budget lines and planning notes for one account."""
    return {"rows": [{"account": account, "cost_centre": cc,
                      "budget": _budget(entity, period, account, cc),
                      "plan_note": _rng("note", entity, account).choice(
                          ["Flat to prior year", "Hiring plan", "Price increase", "One-off project"])}
                     for cc in COST_CENTRES]}


def build_budget() -> MCPServer:
    server = MCPServer(name="budget", instructions="Budget and plan (stub).")
    server.add_tool(plan_lines, name="plan_lines", description=plan_lines.__doc__)
    return server


# ---------- cash: bank statement vs ledger ----------

def _cash(entity: str, date: str) -> list[dict]:
    r = _rng("cash", entity, date)
    rows = []
    for i in range(1, 25):
        cp = r.choice(COUNTERPARTIES)
        rows.append({"ref": f"TX{i:04d}", "counterparty": cp,
                     "counterparty_account": f"GB{zlib.crc32(cp.encode()) % 10**8:08d}",
                     "amount": round(r.uniform(-250_000, 250_000), 2), "value_date": date})
    return rows


def statement(entity: str, date: str) -> dict:
    """Bank statement lines for one entity and value date."""
    r = _rng("bank-diff", entity, date)
    rows = []
    for row in _cash(entity, date):
        roll = r.random()
        if roll < 0.08:
            continue  # missing at the bank
        if roll < 0.18:
            row = {**row, "amount": round(row["amount"] + r.choice([-50.0, 12.5, 2_500.0]), 2)}
        rows.append(row)
    return {"rows": rows}


def postings(entity: str, date: str) -> dict:
    """Ledger cash postings for one entity and value date."""
    rows = _cash(entity, date)
    extra = _rng("ledger-extra", entity, date)
    rows.append({"ref": "TX9001", "counterparty": extra.choice(COUNTERPARTIES),
                 "amount": 75.0, "value_date": date})
    return {"rows": rows}


def counterparty_history(entity: str, date: str, counterparty: str) -> dict:
    """Recent settled items with one counterparty."""
    r = _rng("history", entity, counterparty)
    return {"rows": [{"counterparty": counterparty, "ref": f"H{r.randint(100, 999)}",
                      "amount": round(r.uniform(-50_000, 50_000), 2),
                      "settled": r.choice([True, True, False])} for _ in range(3)]}


def build_bank() -> MCPServer:
    server = MCPServer(name="bank", instructions="Bank statements (stub).")
    server.add_tool(statement, name="statement", description=statement.__doc__)
    return server


def build_ledger() -> MCPServer:
    server = MCPServer(name="ledger", instructions="Ledger cash postings (stub).")
    server.add_tool(postings, name="postings", description=postings.__doc__)
    server.add_tool(counterparty_history, name="counterparty_history",
                    description=counterparty_history.__doc__)
    return server


# ---------- reporting (write) ----------

PUBLISHED: list[dict] = []   # what the stub reporting system received, for tests and demos


def publish_commentary(entity: str, period: str, account: str, commentary: str) -> dict:
    """Publish approved variance commentary for one account to the reporting pack."""
    receipt = f"RPT-{zlib.crc32(f'{entity}|{period}|{account}'.encode()) % 10**6:06d}"
    PUBLISHED.append({"entity": entity, "period": period, "account": account,
                      "commentary": commentary, "receipt": receipt})
    return {"receipt": receipt, "published": True}


def build_reporting() -> MCPServer:
    server = MCPServer(name="reporting", instructions="Management reporting pack (stub).")
    server.add_tool(publish_commentary, name="publish_commentary",
                    description=publish_commentary.__doc__)
    return server


BUILDERS = {"gl": build_gl, "budget": build_budget, "bank": build_bank, "ledger": build_ledger,
            "reporting": build_reporting}


def main() -> None:
    import uvicorn

    p = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    p.add_argument("connector", choices=sorted(BUILDERS))
    p.add_argument("--port", type=int, default=9101)
    a = p.parse_args()
    server = BUILDERS[a.connector]()
    app = server.streamable_http_app(streamable_http_path="/mcp", stateless_http=True,
                                     json_response=True)
    uvicorn.run(app, host="127.0.0.1", port=a.port)


if __name__ == "__main__":
    main()
