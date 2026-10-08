"""A FOBO data set built around the FOBO Investigation Skill v1.0.

Two books on COB 2026-10-09, served by the stub MCP tools (MB Rec, CATS, MOTIF,
security reference) instead of their generated data. Each break is designed so
that one path of the skill decides it; `expected` is the answer the skill gives
when followed exactly (section numbers refer to the skill):

  PRIME-SIM-01 (Complete)
    EMB AMORT 2031    worked example (Appendix A): pull factor 1.00 -> 0.67, CATS shows no
                      redemption PnL, MOTIF -247,000      FO-6 A -> C, DO NOT POST
    GILT 4.25 2045    CATS opened on a stale price         FO-2 -> A, DO NOT POST
    UST 2.5 2029      MOTIF rejected the journal           §8 posting failure, CORRECT & RE-POST
    XYZ STRUCT NOTE   no static, no enrichment, 1.25m     §8 static outlier -> F, DO NOT POST
    BUND 0 2030       yesterday's adjustment rolled forward §8 reapplication -> POST (P1)
    IRS 7Y GBP        settlement booked twice in MOTIF     BO-4 -> D, POST
    ARG 2035          CATS price = 0, restructuring        FO-7 -> G, judgement, ESCALATE
    CORP 5.1 2028     FO and BO pass; MOTIF trade quantity §7 trade level -> E, POST
  PRIME-SIM-02 (In Progress)
    two breaks        R5: do not begin                     ESCALATE (hold)

Used by: the single-session capability (break.investigation.skill, which reads
the components through the tools itself) and the multi-step one
(break.investigation + fobo-prime, which reads mbrec.breaks and the snapshots).
"""

SIM_COB = "2026-10-09"
PREV_COB = "2026-10-08"
SIM_BOOKS = {"PRIME-SIM-01": "Complete", "PRIME-SIM-02": "In Progress"}


def _fo(position, price_prev, price_open, factor_prev, factor_open, fo_pnl, *, mtm_unexplained=0.0,
        trading_pnl_explained=True, redemption_pnl=0.0, holiday_carry_ok=True, price=None, position_open=None):
    return {"position_prev_close": position, "position_open": position if position_open is None else position_open,
            "price_prev_close": price_prev, "price_open": price_open, "price": price_open if price is None else price,
            "pull_factor_prev": factor_prev, "pull_factor_open": factor_open,
            "mtm_unexplained": mtm_unexplained, "trading_pnl_explained": trading_pnl_explained,
            "redemption_pnl": redemption_pnl, "holiday_carry_ok": holiday_carry_ok, "fo_pnl": fo_pnl}


def _bo(position, accounting_price, factor_used, bo_pnl, *, balanced=True, price_source="Bloomberg BVAL",
        factor_ok=True, settled=True, settled_quantity=None, cash_settled=True, cash_ok=True,
        journal="posted", journal_reason=None, settlement_refs=None):
    return {"position_quantity": position, "position_balanced": balanced, "accounting_price": accounting_price,
            "price_source": price_source, "price_source_ok": price_source is not None,
            "factor_used": factor_used, "factor_ok": factor_ok,
            "settled": settled, "settled_quantity": position if settled_quantity is None else settled_quantity,
            "cash_settled": cash_settled, "cash_ok": cash_ok,
            "journal_generated": journal != "not generated", "journal_posted": journal == "posted",
            "journal_rejected": journal == "rejected", "journal_reason": journal_reason,
            "settlement_refs": settlement_refs or [], "bo_pnl": bo_pnl}


BREAKS: dict[str, list[dict]] = {
    "PRIME-SIM-01": [
        {"instrument": "EMB AMORT 2031", "isin": "XS2311110001", "desk": "EM Credit", "age_days": 0,
         "fo": _fo(10_000_000, 98.40, 98.40, 1.00, 0.67, 0.00, redemption_pnl=0.00),
         "bo": _bo(6_700_000, 98.40, 0.67, -247_000.00),
         "ref": {"static_present": True, "amortising": True, "issuer": "EM Sovereign Agency", "currency": "GBP"},
         "corporate_actions": [{"type": "partial redemption", "effective_date": SIM_COB, "factor_from": 1.00,
                                "factor_to": 0.67, "expected_pnl": 247_000.00, "source": "Corporate action file"}],
         "expected": {"category": "C", "secondary": "B", "side": "FO", "verdict": "DO_NOT_POST",
                      "determinism": "deterministic", "decided_at": "FO-6",
                      "finding": "FO-6 finding A: pull factor event missing in CATS"}},
        {"instrument": "GILT 4.25 2045", "isin": "GB00B6460505", "desk": "Rates", "age_days": 0,
         "fo": _fo(15_000_000, 101.243, 101.120, 1.00, 1.00, -18_450.00, mtm_unexplained=-18_450.00),
         "bo": _bo(15_000_000, 101.243, 1.00, 0.00),
         "ref": {"static_present": True, "amortising": False, "issuer": "UK DMO", "currency": "GBP"},
         "corporate_actions": [],
         "expected": {"category": "A", "side": "FO", "verdict": "DO_NOT_POST", "determinism": "deterministic",
                      "decided_at": "FO-2", "finding": "CATS opened on a stale price (101.120 vs close 101.243)"}},
        {"instrument": "UST 2.5 2029", "isin": "US91282CJL54", "desk": "Rates", "age_days": 0,
         "fo": _fo(20_000_000, 97.875, 97.875, 1.00, 1.00, 52_300.00),
         "bo": _bo(20_000_000, 97.875, 1.00, 0.00, journal="rejected",
                   journal_reason="invalid reversal date 2026-10-08"),
         "ref": {"static_present": True, "amortising": False, "issuer": "US Treasury", "currency": "USD"},
         "corporate_actions": [],
         "journal_status": "rejected",
         "expected": {"category": "R", "side": "BO", "verdict": "CORRECT_AND_REPOST", "determinism": "deterministic",
                      "decided_at": "BO-6", "finding": "MOTIF rejected the journal: invalid reversal date"}},
        {"instrument": "XYZ STRUCT NOTE", "isin": None, "desk": "Structured", "age_days": 0,
         "fo": _fo(5_000_000, 100.00, 100.00, 1.00, 1.00, 1_250_000.00),
         "bo": _bo(None, None, None, 0.00, price_source=None, journal="not generated"),
         "ref": {"static_present": False, "amortising": None, "issuer": None, "currency": None},
         "corporate_actions": [],
         "static_present": False,
         "expected": {"category": "F", "side": "BO", "verdict": "DO_NOT_POST", "determinism": "deterministic",
                      "decided_at": "§8 static outlier", "finding": "No static or enrichment data: a false break until validated"}},
        {"instrument": "BUND 0 2030", "isin": "DE0001102499", "desk": "Rates", "age_days": 1,
         "fo": _fo(8_000_000, 88.910, 88.910, 1.00, 1.00, 8_720.15),
         "bo": _bo(8_000_000, 88.910, 1.00, 0.00),
         "ref": {"static_present": True, "amortising": False, "issuer": "Bundesrepublik", "currency": "EUR"},
         "corporate_actions": [],
         "prior_adjustment": 8_720.15,
         "history": [{"cob": PREV_COB, "cobs_ago": 1, "status": "adjusted", "difference": 8_720.15,
                      "adjustment": 8_720.15, "journal": "FOBO-ADJ-55120"}],
         "expected": {"category": "J", "side": "BO", "verdict": "POST", "determinism": "deterministic",
                      "decided_at": "§8 reapplication", "finding": "Today's break equals yesterday's adjustment rolling forward",
                      "needs_confirmation": "materiality_threshold, posting_policy_reference (P1)"}},
        {"instrument": "IRS 7Y GBP", "isin": None, "desk": "Rates", "age_days": 0,
         "fo": _fo(25_000_000, 100.00, 100.00, 1.00, 1.00, 36_800.00),
         "bo": _bo(25_000_000, 100.00, 1.00, 73_600.00, settled=False, cash_ok=False,
                   settlement_refs=["SETTLE-REF-90411", "SETTLE-REF-90411-DUP"]),
         "ref": {"static_present": True, "amortising": False, "issuer": "LCH cleared", "currency": "GBP"},
         "corporate_actions": [],
         "expected": {"category": "D", "side": "BO", "verdict": "POST", "determinism": "deterministic",
                      "decided_at": "BO-4", "finding": "The settlement is booked twice in MOTIF (same reference)"}},
        {"instrument": "ARG 2035", "isin": "US040114HS26", "desk": "EM Credit", "age_days": 0,
         "fo": _fo(4_000_000, 10.30, 0.00, 1.00, 1.00, -412_000.00, price=0.00),
         "bo": _bo(4_000_000, 10.30, 1.00, 0.00),
         "ref": {"static_present": True, "amortising": False, "issuer": "Republic of Argentina", "currency": "USD"},
         "corporate_actions": [{"type": "exchange offer announced", "effective_date": None,
                                "status": "pending holder vote", "source": "Corporate action file"}],
         "expected": {"category": "G", "side": "UNKNOWN", "verdict": "ESCALATE", "determinism": "judgement",
                      "decided_at": "FO-7", "finding": "Price = 0 in CATS; a restructuring is announced but not effective"}},
        {"instrument": "CORP 5.1 2028", "isin": "XS2499990028", "desk": "Credit", "age_days": 0,
         "fo": _fo(2_500_000, 102.10, 102.10, 1.00, 1.00, 21_250.00),
         "bo": _bo(2_500_000, 102.10, 1.00, 17_000.00),
         "ref": {"static_present": True, "amortising": False, "issuer": "Corp Industrial plc", "currency": "GBP"},
         "corporate_actions": [],
         "trades": [{"trade_id": "T-7718201", "cats_quantity": 2_500_000, "motif_quantity": 2_000_000,
                     "direction": "buy", "price": 102.10, "pull_factor": 1.00, "settlement_date": SIM_COB}],
         "expected": {"category": "E", "side": "BO", "verdict": "POST", "determinism": "deterministic",
                      "decided_at": "§7 trade level", "finding": "MOTIF booked trade T-7718201 for 2,000,000, CATS 2,500,000"}},
    ],
    "PRIME-SIM-02": [
        {"instrument": "GILT 1.5 2047", "isin": "GB00BDCHBW80", "desk": "Rates", "age_days": 0,
         "fo": _fo(6_000_000, 61.20, 61.20, 1.00, 1.00, 14_400.00),
         "bo": _bo(6_000_000, 61.20, 1.00, 0.00),
         "ref": {"static_present": True, "amortising": False, "issuer": "UK DMO", "currency": "GBP"},
         "corporate_actions": [],
         "expected": {"category": "W", "side": "UNKNOWN", "verdict": "ESCALATE", "determinism": "deterministic",
                      "decided_at": "R5", "finding": "Book In Progress: investigation must not begin"}},
        {"instrument": "UST 4 2034", "isin": "US91282CJZ59", "desk": "Rates", "age_days": 0,
         "fo": _fo(9_000_000, 99.15, 99.15, 1.00, 1.00, -6_300.00),
         "bo": _bo(9_000_000, 99.15, 1.00, 0.00),
         "ref": {"static_present": True, "amortising": False, "issuer": "US Treasury", "currency": "USD"},
         "corporate_actions": [],
         "expected": {"category": "W", "side": "UNKNOWN", "verdict": "ESCALATE", "determinism": "deterministic",
                      "decided_at": "R5", "finding": "Book In Progress: investigation must not begin"}},
    ],
}


def is_sim(book: str, cob: str) -> bool:
    return book in SIM_BOOKS and cob == SIM_COB


def _breaks(book: str) -> list[dict]:
    return BREAKS[book]


def _pick(book: str, instrument: str | None) -> list[dict]:
    return [b for b in _breaks(book) if instrument in (None, b["instrument"])]


# ---------- what each system's tool returns for the simulation books ----------

def mbrec_breaks(book: str) -> list[dict]:
    status = SIM_BOOKS[book]
    rows = []
    for n, b in enumerate(_breaks(book), start=1):
        fo, bo = b["fo"]["fo_pnl"], b["bo"]["bo_pnl"]
        rows.append({"break_id": f"MBR-SIM-{book[-2:]}{n:02d}", "book": book, "instrument": b["instrument"],
                     "isin": b["isin"], "desk": b["desk"], "break_type": "amount_break",
                     "cats_amount": fo, "motif_amount": bo, "difference": round(fo - bo, 2),
                     "age_days": b["age_days"], "status": "open", "book_status": status,
                     "journal_status": b.get("journal_status", "posted"),
                     "static_present": b.get("static_present", True),
                     "prior_adjustment": b.get("prior_adjustment", 0.0)})
    return rows


def book_status(book: str) -> dict:
    status = SIM_BOOKS[book]
    return {"book": book, "cob": SIM_COB, "status": status, "processed": status == "Complete",
            "available": status == "Complete", "complete": status == "Complete"}


def break_history(book: str, instrument: str) -> list[dict]:
    b = next((x for x in _breaks(book) if x["instrument"] == instrument), None)
    if b is None:
        return []
    return b.get("history") or [{"cob": PREV_COB, "cobs_ago": 1, "status": "none", "difference": 0.0}]


def cats_components(book: str, instrument: str | None) -> list[dict]:
    return [{"instrument": b["instrument"], "isin": b["isin"], **b["fo"]} for b in _pick(book, instrument)]


def motif_components(book: str, instrument: str | None) -> list[dict]:
    return [{"instrument": b["instrument"], "isin": b["isin"], **b["bo"]} for b in _pick(book, instrument)]


def corporate_actions(instrument: str) -> list[dict]:
    for book in BREAKS:
        for b in BREAKS[book]:
            if b["instrument"] == instrument:
                return [{"instrument": instrument, **ca} for ca in b["corporate_actions"]]
    return []


def bond_metadata(instrument: str) -> dict | None:
    for book in BREAKS:
        for b in BREAKS[book]:
            if b["instrument"] == instrument:
                return {"instrument": instrument, "isin": b["isin"], **b["ref"]}
    return None


def trades(book: str, instrument: str | None, side: str) -> list[dict]:
    """CATS or MOTIF trades: one per break, the same on both sides except where
    the break is a booking difference (CORP 5.1 2028)."""
    rows = []
    for n, b in enumerate(_pick(book, instrument), start=1):
        for t in b.get("trades") or [{"trade_id": f"T-SIM{book[-2:]}{n:03d}", "cats_quantity": b["fo"]["position_open"],
                                      "motif_quantity": b["fo"]["position_open"], "direction": "buy",
                                      "price": b["fo"]["price_prev_close"], "pull_factor": b["fo"]["pull_factor_open"],
                                      "settlement_date": PREV_COB}]:
            qty = t["cats_quantity"] if side == "cats" else t["motif_quantity"]
            price = t["price"]
            rows.append({"trade_id": t["trade_id"], "instrument": b["instrument"], "quantity": qty,
                         "direction": t["direction"], "price": price,
                         "consideration": round(qty * price / 100, 2) if qty and price else None,
                         "pull_factor": t["pull_factor"], "settlement_date": t["settlement_date"], "settled": True})
    return rows


def booking_events(book: str, instrument: str | None) -> list[dict]:
    out = []
    for b in _pick(book, instrument):
        bo = b["bo"]
        if bo["journal_rejected"]:
            out.append({"event": "journal rejected", "instrument": b["instrument"], "amount": b["fo"]["fo_pnl"],
                        "booked_at": f"{SIM_COB}T18:42", "reason": bo["journal_reason"]})
        for ref in bo["settlement_refs"]:
            out.append({"event": "settlement entry", "instrument": b["instrument"], "amount": b["fo"]["fo_pnl"],
                        "booked_at": f"{SIM_COB}T16:05", "settlement_ref": ref})
        for t in b.get("trades") or []:
            out.append({"event": "trade booked", "instrument": b["instrument"], "trade_id": t["trade_id"],
                        "quantity": t["motif_quantity"], "booked_at": f"{SIM_COB}T11:20"})
    for n, row in enumerate(out):
        row["event_id"] = f"EV-SIM-{n + 1:03d}"
    return out


def snapshots(book: str) -> list[dict]:
    """The same truth as the components, in the fields the fobo-prime playbook's
    cause checks and tests read (the multi-step setup)."""
    rows = []
    for b in _breaks(book):
        fo, bo, ca = b["fo"], b["bo"], b["corporate_actions"]
        redemption = any("redemption" in c["type"] for c in ca)
        factor_changed = fo["pull_factor_prev"] != fo["pull_factor_open"]
        rows.append({
            "instrument": b["instrument"],
            "fo_booking_ts": f"{SIM_COB}T17:05:00Z", "bo_cutoff_ts": f"{SIM_COB}T23:30:00Z",
            "mapping_present": b["ref"]["static_present"],
            "fo_dataset_id": "CURVE-EOD-0200", "bo_dataset_id": "CURVE-EOD-0200",
            "fo_components": ["principal"], "bo_components": ["principal"],
            "fo_version": 2, "bo_version": 2,
            "fo_adjustments": [], "bo_adjustments": list(bo["settlement_refs"]),
            "fo_prev_close_position": fo["position_prev_close"], "fo_open_position": fo["position_open"],
            "fo_prev_close_price": fo["price_prev_close"], "fo_open_price": fo["price_open"],
            "fo_prev_pull_factor": fo["pull_factor_prev"], "fo_open_pull_factor": fo["pull_factor_open"],
            "mtm_unexplained": fo["mtm_unexplained"], "trade_pnl_explained": fo["trading_pnl_explained"],
            "redemption_event": redemption, "factor_changed": factor_changed,
            "pnl_expected": any(c.get("expected_pnl") for c in ca),
            "cats_calculated": not (redemption and fo["redemption_pnl"] == 0),
            "fo_price": fo["price"], "holiday_carry_ok": fo["holiday_carry_ok"],
            "bo_position_balanced": bo["position_balanced"], "bo_price_source_ok": bo["price_source_ok"],
            "bo_factor_ok": bo["factor_ok"], "bo_settled": bo["settled"], "bo_cash_ok": bo["cash_ok"],
            "bo_journal_posted": bo["journal_posted"],
        })
    return rows
