"""Stand-in bank systems, as real MCP servers, for the skeleton and its tests.

In the office each of these is replaced by the real connector: change its
entry in config/agent-one-finance/connectors.yaml from `transport: inproc` to
`transport: http` with the connector's URL. Nothing else changes.

Data is generated deterministically from the arguments, so every run of the
same case sees the same figures.

Serve one over HTTP, e.g. to try the http transport:
    python -m agent_one_finance.stub_connectors.finance gl --port 9101
"""

import argparse
import functools
import random
import zlib

from mcp.server.mcpserver import MCPServer

from agent_one_finance.stub_connectors import fobo_simulation as sim

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
        # A bank reference is unique to its day; TX9001 (below) is the one
        # ledger item that stays unmatched day after day.
        rows.append({"ref": f"TX{date.replace('-', '')[2:]}-{i:02d}", "counterparty": cp,
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


# ---------- CATS (front office) vs MOTIF (back office) positions ----------

INSTRUMENTS = ["UST 2Y", "UST 10Y", "BUND 10Y", "GILT 5Y", "JGB 10Y", "EURUSD FWD",
               "GBPUSD FWD", "IRS 5Y USD", "IRS 10Y EUR", "CDX IG", "ITRAXX MAIN", "SOFR FUT"]
DESKS = {"UST": "Rates", "BUND": "Rates", "GILT": "Rates", "JGB": "Rates", "IRS": "Rates",
         "EURUSD": "FX", "GBPUSD": "FX", "CDX": "Credit", "ITRAXX": "Credit", "SOFR": "Rates"}


def _fo_positions(book: str, cob: str) -> list[dict]:
    r = _rng("cats", book, cob)
    return [{"book": book, "instrument": ins, "desk": DESKS[ins.split()[0]],
             "quantity": r.randint(1, 500) * 1000,
             "mtm": round(r.uniform(-900_000, 900_000), 2)} for ins in INSTRUMENTS]


def cats_positions(book: str, cob: str) -> dict:
    """Front-office (CATS) end-of-day positions and MTM for one book and COB date."""
    return {"rows": _fo_positions(book, cob)}


def _trades(book: str, cob: str, instrument: str | None) -> list[dict]:
    """The trades behind each FO position: quantity, direction, consideration,
    price, pull factor and settlement — what the skill's §7 validates."""
    rows = []
    for pos in _fo_positions(book, cob):
        if instrument and pos["instrument"] != instrument:
            continue
        r = _rng("trades", book, cob, pos["instrument"])
        for n in range(1, r.randint(2, 4) + 1):
            qty = r.randint(1, 200) * 1000
            price = round(r.uniform(90, 110), 4)
            rows.append({"trade_id": f"T-{zlib.crc32(f'{book}|{pos['instrument']}|{n}'.encode()) % 10**7:07d}",
                         "instrument": pos["instrument"], "quantity": qty,
                         "direction": r.choice(["buy", "sell"]), "price": price,
                         "consideration": round(qty * price / 100, 2), "pull_factor": 1.0,
                         "settlement_date": cob, "settled": r.random() > 0.1})
    return rows


def cats_trades(book: str, cob: str, instrument: str | None = None) -> dict:
    """Front-office (CATS) trades for a book and COB (optionally one instrument)."""
    if sim.is_sim(book, cob):
        return {"rows": sim.trades(book, instrument, "cats")}
    return {"rows": _trades(book, cob, instrument)}


def motif_trades(book: str, cob: str, instrument: str | None = None) -> dict:
    """Back-office (MOTIF) trades for a book and COB (optionally one instrument):
    the same trades as booked in MOTIF — a missing trade, or a different
    quantity, price or pull factor, is what a trade-level investigation finds."""
    if sim.is_sim(book, cob):
        return {"rows": sim.trades(book, instrument, "motif")}
    r = _rng("motif-trades", book, cob)
    rows = []
    for t in _trades(book, cob, instrument):
        roll = r.random()
        if roll < 0.06:
            continue                                         # not in MOTIF
        if roll < 0.12:
            t = {**t, "pull_factor": 0.67}                   # factor applied in MOTIF only
        elif roll < 0.16:
            t = {**t, "quantity": t["quantity"] - 1000,
                 "consideration": round((t["quantity"] - 1000) * t["price"] / 100, 2)}
        rows.append(t)
    return {"rows": rows}


def _motif_base(book: str, cob: str) -> list[dict]:
    r = _rng("motif-diff", book, cob)
    rows = []
    for row in _fo_positions(book, cob):
        roll = r.random()
        if roll < 0.10:
            continue                                         # not booked in MOTIF yet
        if roll < 0.22:
            row = {**row, "mtm": round(row["mtm"] + r.choice([-120.0, 85.5, -15_000.0, 42_000.0]), 2)}
        rows.append(row)
    return rows


# Scenarios the algorithm steps look for, on COBs from this date (earlier COBs
# keep the figures the tests were written against):
#   rebook    an amount booked in MOTIF to the wrong instrument: +A on one, -A on another
#   split     a booking made in MOTIF in two partial bookings, one of them missing today
#   systemic  the same instrument out by about the same amount in about half the books
#   alias     an instrument MOTIF holds under a slightly different name (a typo)
SCENARIOS_FROM = "2026-10-01"
PRIME_BOOKS = [f"PRIME-MB-{n:02d}" for n in range(1, 13)]
RATES_BOOKS = ["RATES-LDN-01", "RATES-LDN-02", "RATES-LDN-03", "RATES-LDN-04", "RATES-NY-01", "RATES-NY-02"]


@functools.lru_cache(maxsize=4096)
def _scenario(book: str, cob: str) -> dict:
    if cob < SCENARIOS_FROM:
        return {}
    fo = {p["instrument"]: p for p in _fo_positions(book, cob)}
    base = {p["instrument"]: p for p in _motif_base(book, cob)}
    clean = [i for i in INSTRUMENTS if i in base and base[i]["mtm"] == fo[i]["mtm"]]
    out: dict = {"alias": sorted(i for i in INSTRUMENTS
                                 if i not in base and _rng("alias", book, cob, i).random() < 0.5)}
    s = _rng("systemic", cob)
    if s.random() < 0.5:
        ins = s.choice(INSTRUMENTS)
        delta = round(s.uniform(20_000, 60_000), 2)
        if ins in clean and _rng("sys-book", book, cob).random() < 0.5:
            out["systemic"] = (ins, round(delta * (1 + _rng("sys-amt", book, cob).uniform(-0.1, 0.1)), 2))
            clean.remove(ins)
    r = _rng("rebook", book, cob)
    if r.random() < 0.35 and len(clean) >= 2:
        i, j = r.sample(clean, 2)
        out["rebook"] = (i, j, round(r.uniform(5_000, 80_000), 2))
        clean = [c for c in clean if c not in (i, j)]
    r = _rng("split", book, cob)
    if r.random() < 0.35 and clean:
        k = r.choice(clean)
        amount = round(r.uniform(10_000, 90_000), 2)
        part = round(amount * r.uniform(0.3, 0.7), 2)
        out["split"] = (k, amount, (part, round(amount - part, 2)))
    return out


def _scenario_instruments(book: str, cob: str) -> set[str]:
    sc = _scenario(book, cob)
    return ({sc["systemic"][0]} if "systemic" in sc else set()) | (set(sc["rebook"][:2]) if "rebook" in sc else set()) \
        | ({sc["split"][0]} if "split" in sc else set())


def motif_positions(book: str, cob: str) -> dict:
    """Back-office (MOTIF) positions and MTM for one book and COB date."""
    if sim.is_sim(book, cob):
        return {"rows": [{"book": book, "instrument": c["instrument"], "quantity": c["position_quantity"],
                          "mtm": c["bo_pnl"]} for c in sim.motif_components(book, None)]}
    rows = _motif_base(book, cob)
    sc = _scenario(book, cob)
    if not sc:
        return {"rows": rows}
    by = {r["instrument"]: dict(r) for r in rows}
    if "systemic" in sc:
        ins, delta = sc["systemic"]
        by[ins]["mtm"] = round(by[ins]["mtm"] - delta, 2)
    if "rebook" in sc:
        i, j, amount = sc["rebook"]
        by[i]["mtm"] = round(by[i]["mtm"] - amount, 2)          # booked to j instead of i
        by[j]["mtm"] = round(by[j]["mtm"] + amount, 2)
    if "split" in sc:
        k, amount, _ = sc["split"]
        by[k]["mtm"] = round(by[k]["mtm"] - amount, 2)          # the second partial booking is missing
    fo = {p["instrument"]: p for p in _fo_positions(book, cob)}
    aliases = [{**fo[i], "instrument": i.replace(" ", "", 1)} for i in sc["alias"]]
    return {"rows": [by[i] for i in INSTRUMENTS if i in by] + aliases}


# The cause each instrument's break has, as FOBO's six cause checks would find
# it (C1–C6), or None for a break no check explains. Deterministic per book/COB.
CAUSES = ["C1", "C2", "C3", "C4", "C5", "C6", None]


def break_snapshots(book: str, cob: str) -> dict:
    """Dated FO/BO snapshots per instrument — what FOBO's cause checks read:
    booking time vs ledger cut-off, static mapping, curve datasets, components,
    trade versions and adjustments on each side."""
    if sim.is_sim(book, cob):
        return {"rows": sim.snapshots(book)}
    rows = []
    scenario = _scenario_instruments(book, cob)
    for ins in INSTRUMENTS:
        cause = None if ins in scenario else _rng("cause", book, cob, ins).choice(CAUSES)
        rows.append({
            "instrument": ins,
            "fo_booking_ts": f"{cob}T23:41:00Z" if cause == "C1" else f"{cob}T17:05:00Z",
            "bo_cutoff_ts": f"{cob}T23:30:00Z",
            "mapping_present": cause != "C2",
            "fo_dataset_id": "CURVE-EOD-0300" if cause == "C3" else "CURVE-EOD-0200",
            "bo_dataset_id": "CURVE-EOD-0200",
            "fo_components": ["principal", "fee"] if cause == "C4" else ["principal"],
            "bo_components": ["principal"],
            "fo_version": 3 if cause == "C5" else 2,
            "bo_version": 2,
            "fo_adjustments": [],
            "bo_adjustments": ["SETTLE-REF-88120", "SETTLE-REF-88120-DUP"] if cause == "C6" else [],
            **_validation_fields(book, cob, ins, "scenario" if ins in scenario else cause),
        })
    return {"rows": rows}


def _validation_fields(book: str, cob: str, ins: str, cause: str | None) -> dict:
    """What FOBO's validation tests read (FO-1…FO-8, BO-1…BO-6, FO-6 findings).
    Mostly clean; a few deterministic failures and gaps in evidence."""
    r = _rng("tests", book, cob, ins)
    pos = r.randint(1, 500) * 1000
    price = round(r.uniform(90, 110), 4)
    factor = round(r.uniform(0.5, 1.0), 6)
    roll = r.random()
    out = {
        "fo_prev_close_position": pos,
        "fo_open_position": pos + (1000 if roll < 0.06 else 0),                 # FO-1
        "fo_prev_close_price": price,
        "fo_open_price": round(price + (0.25 if 0.06 <= roll < 0.10 else 0), 4),  # FO-2
        "fo_prev_pull_factor": factor,
        "fo_open_pull_factor": factor,
        "mtm_unexplained": round(r.uniform(-50, 50), 2),
        "trade_pnl_explained": roll >= 0.04,
        "redemption_event": False, "factor_changed": False,
        "pnl_expected": False, "cats_calculated": True,
        "fo_price": price,
        "holiday_carry_ok": True,
        "bo_position_balanced": True, "bo_price_source_ok": True, "bo_factor_ok": True,
        "bo_settled": cause != "C6", "bo_cash_ok": True,
    }
    if r.random() > 0.2:                     # journal status not always available
        out["bo_journal_posted"] = cause != "C2"
    if cause is None:                        # a break no cause check explains
        kind = r.choice(["redemption_missed", "factor_early", "none"])
        if kind == "redemption_missed":      # FO-6 finding A
            out.update(redemption_event=True, pnl_expected=True, cats_calculated=False,
                       fo_open_pull_factor=round(factor * 0.9, 6), factor_changed=True)
        elif kind == "factor_early":         # FO-6 finding B
            out.update(factor_changed=True, fo_open_pull_factor=round(factor * 0.95, 6))
    return out


def booking_events(book: str, cob: str, break_type: str | None = None,
                   instrument: str | None = None) -> dict:
    """Back-office booking and amendment events behind a book's breaks
    (optionally of one type, or for one instrument)."""
    if sim.is_sim(book, cob):
        return {"rows": sim.booking_events(book, instrument)}
    r = _rng("events", book, cob, break_type or instrument or "all")
    kinds = ["late booking", "price amendment", "FX fixing", "cancel/rebook", "settlement fail"]
    rows = [{"event": r.choice(kinds), "instrument": r.choice(INSTRUMENTS),
             "amount": round(r.uniform(-50_000, 50_000), 2),
             "booked_at": f"{cob}T{r.randint(16, 23):02d}:{r.randint(0, 59):02d}"}
            for _ in range(3)]
    sc = _scenario(book, cob)
    if "split" in sc and not break_type and instrument in (None, sc["split"][0]):
        k, _, parts = sc["split"]
        rows += [{"event": "partial booking", "instrument": k, "amount": p,
                  "booked_at": f"{cob}T{16 + n}:{10 * n + 5:02d}", "status": "pending in MOTIF"}
                 for n, p in enumerate(parts)]
    for n, row in enumerate(rows):
        row["event_id"] = f"EV-{zlib.crc32(f'{book}|{cob}|{n}|{row['instrument']}'.encode()) % 10**6:06d}"
    return {"rows": rows}


def mbrec_book_status(book: str, cob: str) -> dict:
    """Whether MB Rec has processed the book for the COB: Complete, In Progress,
    Waiting or Failed (skill R5: investigate only Processed, Available, Complete books)."""
    if sim.is_sim(book, cob):
        return {"rows": [sim.book_status(book)]}
    status = "In Progress" if _rng("book-status", book, cob).random() < 0.03 else "Complete"
    return {"rows": [{"book": book, "cob": cob, "status": status, "processed": status == "Complete",
                      "available": status == "Complete", "complete": status == "Complete"}]}


def cats_pnl_components(book: str, cob: str, instrument: str | None = None) -> dict:
    """FO (CATS) PnL decomposed per instrument: prior close and open position,
    price and pull factor, MTM not explained by position x price movement, whether
    trade economics explain Trading PnL, redemption PnL, holiday carry and FO PnL."""
    if sim.is_sim(book, cob):
        return {"rows": sim.cats_components(book, instrument)}
    rows = []
    for s in break_snapshots(book, cob)["rows"]:
        if instrument and s["instrument"] != instrument:
            continue
        fo = next(p for p in _fo_positions(book, cob) if p["instrument"] == s["instrument"])
        rows.append({"instrument": s["instrument"], "position_prev_close": s["fo_prev_close_position"],
                     "position_open": s["fo_open_position"], "price_prev_close": s["fo_prev_close_price"],
                     "price_open": s["fo_open_price"], "price": s["fo_price"],
                     "pull_factor_prev": s["fo_prev_pull_factor"], "pull_factor_open": s["fo_open_pull_factor"],
                     "mtm_unexplained": s["mtm_unexplained"], "trading_pnl_explained": s["trade_pnl_explained"],
                     "redemption_pnl": 0.0, "holiday_carry_ok": s["holiday_carry_ok"], "fo_pnl": fo["mtm"]})
    return {"rows": rows}


def motif_pnl_components(book: str, cob: str, instrument: str | None = None) -> dict:
    """BO (MOTIF) PnL decomposed per instrument: position balance and quantity,
    accounting price and source, pull factor used, settlement (settled, quantity,
    cash), cash movements, journal (generated, posted, rejected and why) and BO PnL."""
    if sim.is_sim(book, cob):
        return {"rows": sim.motif_components(book, instrument)}
    bo = {p["instrument"]: p for p in motif_positions(book, cob)["rows"]}
    rows = []
    for s in break_snapshots(book, cob)["rows"]:
        if instrument and s["instrument"] != instrument:
            continue
        rows.append({"instrument": s["instrument"], "position_balanced": s["bo_position_balanced"],
                     "price_source_ok": s["bo_price_source_ok"], "factor_ok": s["bo_factor_ok"],
                     "settled": s["bo_settled"], "cash_ok": s["bo_cash_ok"],
                     "journal_posted": s.get("bo_journal_posted"), "settlement_refs": s["bo_adjustments"],
                     "bo_pnl": bo[s["instrument"]]["mtm"] if s["instrument"] in bo else None})
    return {"rows": rows}


def corporate_actions(instrument: str, cob: str) -> dict:
    """Corporate actions for an instrument around a COB: redemptions and pull factor
    changes (factor from and to, expected PnL), restructurings, exchange offers."""
    return {"rows": sim.corporate_actions(instrument)}


def bond_metadata(instrument: str) -> dict:
    """Static and enrichment data for an instrument: ISIN, issuer, currency,
    amortising or not, and whether static data exists at all."""
    found = sim.bond_metadata(instrument)
    if found is None:
        found = {"instrument": instrument, "isin": None, "static_present": instrument in INSTRUMENTS,
                 "amortising": False}
    return {"rows": [found]}


def build_secref() -> MCPServer:
    server = MCPServer(name="secref", instructions="Security reference: corporate actions and bond metadata (stub).")
    server.add_tool(corporate_actions, name="corporate_actions", description=corporate_actions.__doc__)
    server.add_tool(bond_metadata, name="bond_metadata", description=bond_metadata.__doc__)
    return server


def build_cats() -> MCPServer:
    server = MCPServer(name="cats", instructions="CATS front-office positions (stub).")
    server.add_tool(cats_positions, name="positions", description=cats_positions.__doc__)
    server.add_tool(cats_trades, name="trades", description=cats_trades.__doc__)
    server.add_tool(cats_pnl_components, name="pnl_components", description=cats_pnl_components.__doc__)
    return server


def build_motif() -> MCPServer:
    server = MCPServer(name="motif", instructions="MOTIF back-office positions and events (stub).")
    server.add_tool(motif_positions, name="positions", description=motif_positions.__doc__)
    server.add_tool(booking_events, name="booking_events", description=booking_events.__doc__)
    server.add_tool(motif_trades, name="trades", description=motif_trades.__doc__)
    server.add_tool(break_snapshots, name="break_snapshots", description=break_snapshots.__doc__)
    server.add_tool(motif_pnl_components, name="pnl_components", description=motif_pnl_components.__doc__)
    server.add_tool(break_snapshots_named_pnl, name="break_snapshots_named_pnl",
                    description=break_snapshots_named_pnl.__doc__)
    return server


# ---------- MB Rec: the reconciliation system FOBO's breaks come from ----------
# MB Rec has already matched CATS to MOTIF; Agent One Finance reads its open breaks and
# investigates them. It never re-matches the positions itself.

# Test hook: breaks MB Rec raises later in the day for a book and COB, as if a
# controller or a re-run added exceptions after the first notification.
LATE_BREAKS: dict[tuple[str, str], list[dict]] = {}


def _open_breaks(book: str, cob: str) -> list[dict]:
    fo = {r["instrument"]: r for r in _fo_positions(book, cob)}
    bo = {r["instrument"]: r for r in motif_positions(book, cob)["rows"]}
    rows = []
    for ins, f in fo.items():
        b = bo.get(ins)
        diff = round(f["mtm"] - (b["mtm"] if b else 0.0), 2)
        if b is not None and abs(diff) <= 0.5:
            continue
        cause = _rng("cause", book, cob, ins).choice(CAUSES)
        # A late booking is usually new (a timing difference that should clear
        # on the next COB); other breaks may have been open for a while.
        age = 0 if cause == "C1" or ins in _scenario_instruments(book, cob) else _rng("age", book, cob, ins).choice([0, 0, 1, 2, 4])
        # What the skill's scenario checks read (§3 R5, §8): rare, deterministic.
        x = _rng("mbrec-scenario", book, cob, ins).random()
        rows.append({"break_id": f"MBR-{zlib.crc32(f'{book}|{ins}'.encode()) % 10**6:06d}",
                     "book": book, "instrument": ins, "desk": f["desk"],
                     "break_type": "missing_motif" if b is None else "amount_break",
                     "cats_amount": f["mtm"], "motif_amount": b["mtm"] if b else None,
                     "difference": diff, "age_days": age, "status": "open",
                     "book_status": "In Progress" if _rng("book-status", book, cob).random() < 0.03 else "Complete",
                     "journal_status": "rejected" if x < 0.05 else "posted",
                     "static_present": not (0.05 <= x < 0.09),
                     "prior_adjustment": diff if 0.09 <= x < 0.14 else 0.0})
    return rows + LATE_BREAKS.get((book, cob), [])


def mbrec_breaks(book: str, cob: str) -> dict:
    """Open breaks MB Rec reconciled for one book and COB: CATS vs MOTIF amounts,
    the difference, the break type and how many COBs it has been open."""
    if sim.is_sim(book, cob):
        return {"rows": sim.mbrec_breaks(book)}
    return {"rows": _open_breaks(book, cob)}


def mbrec_break_history(book: str, cob: str, instrument: str) -> dict:
    """The last five COBs of one instrument's break in MB Rec: open or cleared,
    and the difference — to tell a timing difference that clears from one that stays."""
    if sim.is_sim(book, cob):
        return {"rows": [{"instrument": instrument, **h} for h in sim.break_history(book, instrument)]}
    r = _rng("history", book, instrument)
    return {"rows": [{"instrument": instrument, "cobs_ago": n,
                      "status": r.choice(["open", "cleared", "cleared"]),
                      "difference": round(r.uniform(-50_000, 50_000), 2)} for n in range(1, 6)]}


def mbrec_break_history_book(book: str, cob: str) -> dict:
    """The last five COBs of every open break in a book: one row per instrument
    and COB (cobs_ago 1 = the previous COB), open or cleared, and the difference."""
    rows = []
    for b in mbrec_breaks(book, cob)["rows"]:
        rows += mbrec_break_history(book, cob, b["instrument"])["rows"]
    return {"rows": rows}


def mbrec_breaks_all(cob: str) -> dict:
    """Open breaks in every Prime and Rates book for one COB (book, instrument,
    difference only): to see whether a break is one book's or everyone's."""
    return {"rows": [{"book": b["book"], "instrument": b["instrument"], "difference": b["difference"]}
                     for book in PRIME_BOOKS + RATES_BOOKS for b in _open_breaks(book, cob)]}


# ---------- Named P&L: several master books worked as one case ----------
# A named P&L groups master books (the books MB Rec reconciles). These tools
# return every master book's rows in one call, each row naming its book, so a
# case keyed by named P&L and COB reads them the way a case per book does.

NAMED_PNLS = {
    "PRIME-FINANCING-EMEA": ["PRIME-MB-01", "PRIME-MB-02", "PRIME-MB-03"],
    "PRIME-FINANCING-US": ["PRIME-MB-04", "PRIME-MB-05", "PRIME-MB-06"],
}


def _master_books(named_pnl: str) -> list[str]:
    if named_pnl not in NAMED_PNLS:
        raise ValueError(f"unknown named P&L {named_pnl!r}")
    return NAMED_PNLS[named_pnl]


def mbrec_named_pnl_books(named_pnl: str, cob: str) -> dict:
    """The master books in a named P&L: MB Rec's status for each on the COB
    (Complete, In Progress, ...) and how many open breaks it has."""
    return {"rows": [{"named_pnl": named_pnl, "book": b, "status": mbrec_book_status(b, cob)["rows"][0]["status"],
                      "open_breaks": len(mbrec_breaks(b, cob)["rows"])} for b in _master_books(named_pnl)]}


def mbrec_breaks_named_pnl(named_pnl: str, cob: str) -> dict:
    """Open breaks MB Rec reconciled for every master book in a named P&L on one
    COB. Each row names its master book (`book`); `break_id` is unique across them."""
    return {"rows": [{**r, "named_pnl": named_pnl} for b in _master_books(named_pnl)
                     for r in mbrec_breaks(b, cob)["rows"]]}


def break_snapshots_named_pnl(named_pnl: str, cob: str) -> dict:
    """The dated FO/BO snapshots of every master book in a named P&L on one COB,
    one row per book and instrument (join on both)."""
    return {"rows": [{**r, "book": b} for b in _master_books(named_pnl)
                     for r in break_snapshots(b, cob)["rows"]]}


def build_mbrec() -> MCPServer:
    server = MCPServer(name="mbrec", instructions="MB Rec reconciled breaks (stub).")
    server.add_tool(mbrec_breaks, name="breaks", description=mbrec_breaks.__doc__)
    server.add_tool(mbrec_break_history, name="break_history", description=mbrec_break_history.__doc__)
    server.add_tool(mbrec_break_history_book, name="break_history_book", description=mbrec_break_history_book.__doc__)
    server.add_tool(mbrec_breaks_all, name="breaks_all", description=mbrec_breaks_all.__doc__)
    server.add_tool(mbrec_book_status, name="book_status", description=mbrec_book_status.__doc__)
    server.add_tool(mbrec_named_pnl_books, name="named_pnl_books", description=mbrec_named_pnl_books.__doc__)
    server.add_tool(mbrec_breaks_named_pnl, name="breaks_named_pnl", description=mbrec_breaks_named_pnl.__doc__)
    return server


# ---------- reporting (write) ----------

PUBLISHED: list[dict] = []   # what the stub reporting system received, for tests and demos


# Test hook: accounts whose publish fails, as if the reporting system were down.
FAIL_ACCOUNTS: set[str] = set()


def publish_commentary(entity: str, period: str, account: str, commentary: str,
                       idempotency_key: str | None = None) -> dict:
    """Publish approved variance commentary for one account to the reporting pack.
    A repeat with the same idempotency key returns the first receipt."""
    if account in FAIL_ACCOUNTS:
        raise RuntimeError(f"reporting pack unavailable for {account}")
    if idempotency_key:
        for p in PUBLISHED:
            if p.get("idempotency_key") == idempotency_key:
                return {"receipt": p["receipt"], "published": True, "replayed": True}
    receipt = f"RPT-{zlib.crc32(f'{entity}|{period}|{account}'.encode()) % 10**6:06d}"
    PUBLISHED.append({"entity": entity, "period": period, "account": account,
                      "commentary": commentary, "receipt": receipt,
                      "idempotency_key": idempotency_key})
    return {"receipt": receipt, "published": True}


def build_reporting() -> MCPServer:
    server = MCPServer(name="reporting", instructions="Management reporting pack (stub).")
    server.add_tool(publish_commentary, name="publish_commentary",
                    description=publish_commentary.__doc__)
    return server


# ---------- ticketing (ServiceNow / Jira stand-in) ----------

TICKETS: list[dict] = []


def create_ticket(team: str, title: str, description: str = "", priority: str = "P3",
                  idempotency_key: str | None = None) -> dict:
    """Raise a ticket for a team's queue. A repeat with the same idempotency key
    returns the first ticket."""
    if idempotency_key:
        for t in TICKETS:
            if t.get("idempotency_key") == idempotency_key:
                return {**{k: t[k] for k in ("reference", "url", "team")}, "replayed": True}
    reference = f"INC{zlib.crc32((idempotency_key or title).encode()) % 10**7:07d}"
    ticket = {"reference": reference, "url": f"https://tickets.example/{reference}", "team": team,
              "title": title, "description": description, "priority": priority,
              "idempotency_key": idempotency_key}
    TICKETS.append(ticket)
    return {k: ticket[k] for k in ("reference", "url", "team")}


def build_ticketing() -> MCPServer:
    server = MCPServer(name="ticketing", instructions="Team ticket queues (stub).")
    server.add_tool(create_ticket, name="create_ticket", description=create_ticket.__doc__)
    return server


BUILDERS = {"ticketing": build_ticketing, "gl": build_gl, "budget": build_budget, "bank": build_bank, "ledger": build_ledger,
            "reporting": build_reporting, "cats": build_cats, "motif": build_motif,
            "mbrec": build_mbrec, "secref": build_secref}


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
