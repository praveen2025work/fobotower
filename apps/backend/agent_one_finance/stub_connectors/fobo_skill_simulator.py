"""A simulated model that follows the FOBO Investigation Skill v1.0 exactly.

Not a language model: a deterministic stand-in that does what the skill says,
step by step, through the same MCP tools and gateway a real model uses, and
writes the skill's §12 output. It gives the answers the skill expects, so a
simulation shows both setups end to end without a model, and a real model's
answers can later be scored against these (an eval).

    AOF_LLM_ADAPTER=agent_one_finance.stub_connectors.fobo_skill_simulator:FoboSkillSimulator

  investigate()  the single-step capability (one session): reads the book status,
                 the break universe, FO and BO components, corporate actions,
                 bond metadata, break history and trades, then decides each break.
  reason()       the multi-step capability: the playbook already ran; for the
                 judgement groups it reads the tests on each break and the trades.
"""

from agent_one_finance.llm import ReasonResult, SessionResult, StubLlm

VERDICT_WORDS = {"POST": "POST", "DO_NOT_POST": "DO NOT POST", "ESCALATE": "ESCALATE",
                 "CORRECT_AND_REPOST": "CORRECT & RE-POST", "MONITOR": "MONITOR"}
CATEGORY = {"A": "Price break", "B": "Pull factor break", "C": "Redemption break", "D": "Settlement break",
            "E": "Trade booking break", "F": "Data quality break", "G": "Corporate action break", "H": "Novel break",
            "R": "Posting failure (§8)", "J": "Reapplication (§8)", "W": "Not investigated (R5)"}


def _money(v) -> str:
    return f"{v:,.2f}"


class _Session:
    """One session's transcript and tool calls."""

    def __init__(self, tools, case_key: dict):
        self.tools, self.case_key, self.transcript, self.turn = tools, case_key, [], 0

    def say(self, text: str) -> None:
        self.turn += 1
        self.transcript.append({"turn": self.turn, "role": "model", "kind": "text", "text": text})

    async def call(self, tool: str, **args) -> list[dict]:
        self.transcript.append({"turn": self.turn, "role": "model", "kind": "tool_call", "tool": tool, "input": args})
        rows = (await self.tools(tool, args)).get("rows", []) or []
        self.transcript.append({"turn": self.turn, "role": "tool", "kind": "tool_result", "tool": tool, "rows": len(rows)})
        return rows


def _check(test: str, what: str, result: str, evidence: str) -> str:
    return f"{test} | {what} | {result} | {evidence}"


async def _decide(s: _Session, br: dict, fo: dict, bo: dict, book: str, cob: str, allowed: set[str]) -> dict:
    """The skill's §4 sequence for one break. Returns the result with §12 sections."""
    ins, diff = br["instrument"], br["difference"]
    checks: list[str] = []
    not_done: list[str] = []
    out = {"root_cause": "", "category": "H", "secondary": None, "side": "UNKNOWN", "determinism": "judgement",
           "verdict": "ESCALATE", "remediation": "", "end_state": "", "conditional": None}

    def done(**kw):
        out.update(kw)
        return out

    # §8 static outlier: no static, no enrichment, no reference data.
    if not br.get("static_present", True) and "secref.bond_metadata" in allowed:
        meta = (await s.call("secref.bond_metadata", instrument=ins) or [{}])[0]
        checks.append(_check("§8 static", "Static and enrichment data for the instrument",
                             "Fail" if not meta.get("static_present") else "Pass", "Bond metadata"))
        if not meta.get("static_present"):
            return done(root_cause=f"Static outlier: {ins} has no static, enrichment or reference data, and MOTIF "
                                   f"generated no entry; the break of {_money(diff)} has no instrument support.",
                        category="F", side="BO", determinism="deterministic", verdict="DO_NOT_POST",
                        remediation="Treat as a false break until validated. Raise a static data request with "
                                    "Technology and Operations; confirm whether the instrument should exist in MOTIF.",
                        end_state="No adjustment posted; the break stays open until static data is set up, then is re-tested.",
                        checks=checks, not_done=["FO and BO component tests: no reference data to test against"])

    # §8 reapplication: today's break is yesterday's adjustment rolling forward.
    if br.get("prior_adjustment") and "mbrec.break_history" in allowed:
        hist = await s.call("mbrec.break_history", book=book, cob=cob, instrument=ins)
        prior = next((h for h in hist if h.get("adjustment")), None)
        same = prior is not None and abs(prior["adjustment"] - diff) < 0.01
        checks.append(_check("§8 reapplication", "Prior journal, previous break and current break",
                             "Match" if same else "No match", "MB Rec break history"))
        if same:
            return done(root_cause=f"Reapplication: today's break of {_money(diff)} equals the adjustment posted on the "
                                   f"previous COB ({prior['journal']}, {_money(prior['adjustment'])}) rolling forward.",
                        category="J", side="BO", determinism="deterministic", verdict="POST",
                        conditional="Rule P1: the materiality threshold and posting policy reference are not confirmed; "
                                    "POST is conditional on Product Control confirming them.",
                        remediation="Re-post the carried-forward adjustment. Ask Operations why the adjustment does not "
                                    "roll automatically; propose an MB Rec rule to auto-reapply carried-forward adjustments.",
                        end_state="After posting, re-test BO + adjustments = FO on the next COB.",
                        checks=checks, not_done=[])

    # Step 2: FO validation (R2: never assume FO is correct).
    s.say(f"{ins}: validating front office first (R2).")
    fo_fail = None
    checks.append(_check("FO-1", "Prior close position = open position",
                         "Pass" if fo["position_prev_close"] == fo["position_open"] else "Fail", "Position file"))
    if fo["position_prev_close"] != fo["position_open"]:
        fo_fail = fo_fail or "FO-1"
    p_ok = fo["price_prev_close"] == fo["price_open"]
    checks.append(_check("FO-2", f"Close price {fo['price_prev_close']} = open price {fo['price_open']}",
                         "Pass" if p_ok else "Fail", "Pricing file"))
    f_ok = fo["pull_factor_prev"] == fo["pull_factor_open"]
    checks.append(_check("FO-3", f"Pull factor {fo['pull_factor_prev']:.2f} -> {fo['pull_factor_open']:.2f}",
                         "Pass" if f_ok else "Fail", "Pull factor history"))
    if fo["mtm_unexplained"] == 0:
        checks.append(_check("FO-4", "Position x price movement explains MTM", "Pass", "Position and pricing files"))
    else:
        checks.append(_check("FO-4", f"MTM not explained by position x price: {_money(fo['mtm_unexplained'])}",
                             "Fail (tolerance not confirmed, P1)", "Position and pricing files"))
    checks.append(_check("FO-5", "Trade economics explain Trading PnL",
                         "Pass" if fo["trading_pnl_explained"] else "Fail", "Trade file"))
    checks.append(_check("FO-8", "Holiday carry-forward", "Pass" if fo["holiday_carry_ok"] else "Fail", "Pricing file"))

    # FO-7: Price = 0 may be a valid corporate action — obtain evidence first.
    if fo["price"] == 0:
        acts = await s.call("secref.corporate_actions", instrument=ins, cob=cob) if "secref.corporate_actions" in allowed else []
        effective = [a for a in acts if a.get("effective_date")]
        checks.append(_check("FO-7", "Price = 0: valid corporate action or data quality?",
                             "Unable to conclude", "Corporate action file" + (f": {acts[0]['type']}, {acts[0].get('status')}" if acts else ": none")))
        return done(root_cause=f"Not established. CATS values {ins} at price 0 (prior close {fo['price_prev_close']}), giving "
                               f"FO PnL {_money(fo['fo_pnl'])}. The corporate action file shows "
                               + (f"'{acts[0]['type']}' ({acts[0].get('status')}), not yet effective" if acts and not effective else "no event")
                               + ". First hypothesis: CATS wrote the position down ahead of the restructuring (FO data issue, "
                                 "DO NOT POST). Second hypothesis: a valid zero price under the exchange terms (BO behind). "
                                 "Evidence that would confirm: the exchange offer terms and the trade file.",
                    category="G", side="UNKNOWN", determinism="judgement", verdict="ESCALATE",
                    remediation="SME review (R7). Ask CATS support and market data for the price source; obtain the "
                                "exchange offer terms and bond metadata before any adjustment.",
                    end_state="Investigation remains open; no adjustment until the price is evidenced.",
                    checks=checks, not_done=["BO tests not run: FO not validated (FO-7 unresolved)"])

    # FO-6: redemption analysis when the pull factor moved.
    if not f_ok:
        acts = await s.call("secref.corporate_actions", instrument=ins, cob=cob) if "secref.corporate_actions" in allowed else []
        red = next((a for a in acts if "redemption" in a["type"]), None)
        if red and fo["redemption_pnl"] == 0 and red.get("expected_pnl"):
            checks.append(_check("FO-6", "Redemption occurred; factor changed; PnL expected; CATS calculated it?",
                                 "Fail (finding A)", f"Corporate action file: expected PnL {_money(red['expected_pnl'])}; CATS 0.00"))
            return done(root_cause=f"Front office. CATS did not generate redemption PnL on the pull factor movement "
                                   f"{fo['pull_factor_prev']:.2f} -> {fo['pull_factor_open']:.2f}; expected {_money(red['expected_pnl'])}. "
                                   f"MOTIF correctly reflected {_money(bo['bo_pnl'])}. FO-6 finding A: pull factor event missing.",
                        category="C", secondary="B", side="FO", determinism="deterministic", verdict="DO_NOT_POST",
                        remediation="Notify the desk and product controllers; escalate to CATS support as a calculation "
                                    "failure on redemption events; raise a DQ incident with root-cause analysis. Check other "
                                    "amortising positions with factor moves on the same date (systemic?). Propose an MB Rec "
                                    "rule: factor movement present and redemption PnL absent in FO -> auto-exception.",
                        end_state="Not applicable: no adjustment posted. Open pending the FO correction, then re-test "
                                  "BO + adjustments = FO.",
                        checks=checks, not_done=["BO-1 to BO-6: not required, FO root cause established at FO-6"])
        checks.append(_check("FO-6", "Factor changed without a redemption", "Fail (finding B)", "Corporate action file"))
        return done(root_cause="Front office: CATS applied the pull factor before the event's effective date (finding B).",
                    category="B", side="FO", determinism="deterministic", verdict="DO_NOT_POST",
                    remediation="Escalate to CATS support; raise a DQ incident.",
                    end_state="No adjustment; open pending the FO correction.", checks=checks, not_done=[])

    if not p_ok:
        return done(root_cause=f"Front office. CATS opened {ins} at {fo['price_open']} against a prior close of "
                               f"{fo['price_prev_close']} (FO-2 price continuity), creating MTM of {_money(fo['mtm_unexplained'])} "
                               f"that the position and price movement do not explain. MOTIF is on {bo['accounting_price']}.",
                    category="A", side="FO", determinism="deterministic", verdict="DO_NOT_POST",
                    remediation="Raise a market-data DQ incident; ask CATS support why the price did not propagate; "
                                "propose an MB Rec check on open price = prior close.",
                    end_state="No adjustment posted; re-test when CATS reprices.",
                    checks=checks, not_done=["BO tests: not required, FO root cause established at FO-2"])

    # Step 3: BO validation.
    s.say(f"{ins}: front office passes; validating back office.")
    refs = bo.get("settlement_refs") or []
    checks += [
        _check("BO-1", "Position balance and quantity", "Pass" if bo["position_balanced"] else "Fail", "MOTIF position"),
        _check("BO-2", f"Accounting price {bo['accounting_price']} from {bo['price_source']}",
               "Pass" if bo["price_source_ok"] else "Fail", "Pricing source"),
        _check("BO-3", "Pull factor used", "Pass" if bo["factor_ok"] else "Fail", "MOTIF factor"),
        _check("BO-4", "Settled once, quantity and cash", "Pass" if bo["settled"] else "Fail",
               "Settlement records" + (f": {', '.join(refs)}" if refs else "")),
        _check("BO-5", "Cash movements", "Pass" if bo["cash_ok"] else "Fail", "Cash records"),
        _check("BO-6", "Journal generated and posted", "Rejected" if bo["journal_rejected"] else
               ("Pass" if bo["journal_posted"] else "Fail"), "Journal status"),
    ]
    if bo["journal_rejected"]:
        return done(root_cause=f"Back office: MOTIF rejected the journal ({bo['journal_reason']}); FO PnL "
                               f"{_money(fo['fo_pnl'])} is correct and BO shows {_money(bo['bo_pnl'])}.",
                    category="R", side="BO", determinism="deterministic", verdict="CORRECT_AND_REPOST",
                    remediation="A mechanical failure, not a posting judgement (§8): correct the reversal date and "
                                "re-post. Ask Operations why the reversal date was invalid.",
                    end_state="After re-posting, confirm BO + adjustments = FO on the next COB.", checks=checks, not_done=[])
    if not bo["settled"] or len(refs) > 1:
        return done(root_cause=f"Back office: the settlement is booked twice in MOTIF ({', '.join(refs)}), doubling BO "
                               f"PnL to {_money(bo['bo_pnl'])} against FO {_money(fo['fo_pnl'])}.",
                    category="D", side="BO", determinism="deterministic", verdict="POST",
                    conditional="Rule P1: the posting policy reference is not confirmed; POST needs controller confirmation.",
                    remediation="Settlement repair with Operations: reverse the duplicate entry; post the FOBO adjustment "
                                "until MOTIF is corrected.",
                    end_state="After posting, BO + adjustments must equal FO; re-test on the next COB.", checks=checks, not_done=[])

    # Step 4: trade level (both sides look right, the break persists).
    s.say(f"{ins}: FO and BO both pass, the break persists — trade-level investigation (§7).")
    if "cats.trades" in allowed and "motif.trades" in allowed:
        ft = {t["trade_id"]: t for t in await s.call("cats.trades", book=book, cob=cob, instrument=ins)}
        bt = {t["trade_id"]: t for t in await s.call("motif.trades", book=book, cob=cob, instrument=ins)}
        for tid, t in ft.items():
            b = bt.get(tid)
            if b and b["quantity"] != t["quantity"]:
                checks.append(_check("Trade", f"{tid}: quantity CATS {t['quantity']:,} vs MOTIF {b['quantity']:,}",
                                     "Fail", "Trade file"))
                return done(root_cause=f"Back office booking: MOTIF booked {tid} for {b['quantity']:,} against "
                                       f"{t['quantity']:,} in CATS; FO trade economics explain Trading PnL (FO-5 pass).",
                            category="E", side="BO", determinism="deterministic", verdict="POST",
                            conditional="Rule P1: materiality and posting policy are not confirmed; POST needs confirmation.",
                            remediation="Operations to amend the MOTIF booking; post the FOBO adjustment until amended.",
                            end_state="Re-test BO + adjustments = FO after the amendment.", checks=checks, not_done=[])
    return done(root_cause="Not established: FO, BO and trade-level tests pass; a novel break.",
                category="H", verdict="ESCALATE", remediation="Capture for skill evolution; SME review.",
                end_state="Investigation remains open.", checks=checks, not_done=[])


def _sections(br: dict, fo: dict | None, bo: dict | None, d: dict, book: str, cob: str) -> dict:
    verdict = VERDICT_WORDS[d["verdict"]]
    summary = (f"{br['instrument']} ({br.get('isin') or 'no ISIN'}), desk {br['desk']}, book {book}, COB {cob}. "
               f"FO {_money(br['cats_amount'])}, BO {_money(br['motif_amount'])}, break {_money(br['difference'])}.")
    return {
        "break_summary": summary,
        "checks": "\n".join(d.get("checks") or []) + ("\nNot performed: " + "; ".join(d["not_done"]) if d.get("not_done") else ""),
        "root_cause": d["root_cause"],
        "classification": f"{d['category']} — {CATEGORY.get(d['category'], d['category'])}"
                          + (f" (secondary {d['secondary']} — {CATEGORY[d['secondary']]})" if d.get("secondary") else "")
                          + f". {d['determinism'].capitalize()}" + ("; for SME review (R7)." if d["determinism"] == "judgement" else "."),
        "verdict": f"{verdict}." + (f" {d['conditional']}" if d.get("conditional") else ""),
        "remediation": d["remediation"],
        "end_state": d["end_state"],
    }


class FoboSkillSimulator(StubLlm):
    name = "fobo-skill-simulator"

    async def investigate(self, request, tools):
        key = request.case_key
        book, cob = key["book"], key["cob"]
        allowed = set(request.allowed_tools)
        s = _Session(tools, key)
        s.transcript.append({"turn": 0, "role": "user", "kind": "prompt",
                             "text": f"Investigate each break for book {book}, COB {cob}, following the FOBO skill."})
        s.say("Step 0: confirm processing is complete (R5).")
        status = (await s.call("mbrec.book_status", book=book, cob=cob) or [{}])[0]
        s.say("Step 1: establish the break universe.")
        breaks = await s.call("mbrec.breaks", book=book, cob=cob)
        if status.get("status") != "Complete":
            s.say(f"The book is {status.get('status')}: R5, do not begin. Every break is held.")
            results = [{"id": b["instrument"], "status": "escalated", "verdict": "ESCALATE",
                        "reason": f"R5: book {status.get('status')}",
                        "comment": f"R5: {book} is {status.get('status')} in MB Rec; investigation must not begin.",
                        "sections": {"break_summary": f"{b['instrument']}, break {_money(b['difference'])}.",
                                     "checks": "Step 0 | Book processing complete? | Fail | MB Rec book status",
                                     "root_cause": "Not investigated: the book is not complete (R5).",
                                     "classification": "Not classified (R5).",
                                     "verdict": "ESCALATE: hold until MB Rec completes the book.",
                                     "remediation": "Ask Operations when MB Rec will complete the book; re-run then.",
                                     "end_state": "Not started."},
                        "fields": {"isin": b.get("isin"), "category": "W", "determinism": "deterministic",
                                   "difference": b["difference"]}} for b in breaks]
            s.transcript.append({"turn": s.turn, "role": "model", "kind": "answer",
                                 "text": f"{len(results)} breaks held under R5."})
            return SessionResult(results=results, summary=f"{book} is {status.get('status')}: R5, nothing investigated.",
                                 model=self.name, transcript=s.transcript)
        s.say("Step 2-3: read the FO and BO PnL components for the book.")
        fo = {r["instrument"]: r for r in await s.call("cats.pnl_components", book=book, cob=cob)}
        bo = {r["instrument"]: r for r in await s.call("motif.pnl_components", book=book, cob=cob)}
        results = []
        for br in breaks:
            ins = br["instrument"]
            d = await _decide(s, br, fo.get(ins, {}), bo.get(ins, {}), book, cob, allowed)
            s.say(f"{ins}: {CATEGORY.get(d['category'])}, {VERDICT_WORDS[d['verdict']]}.")
            results.append({"id": ins, "status": "escalated" if d["verdict"] == "ESCALATE" else "proposed",
                            "verdict": d["verdict"], "reason": "Root cause not established; SME review" if d["verdict"] == "ESCALATE" else None,
                            "comment": d["root_cause"], "sections": _sections(br, fo.get(ins), bo.get(ins), d, book, cob),
                            "fields": {"isin": br.get("isin"), "category": d["category"], "side": d["side"],
                                       "determinism": d["determinism"], "difference": br["difference"]}})
        counts = {}
        for r in results:
            counts[r["verdict"]] = counts.get(r["verdict"], 0) + 1
        summary = f"{len(results)} breaks in {book}: " + ", ".join(f"{n} {VERDICT_WORDS[v]}" for v, n in sorted(counts.items())) + "."
        s.transcript.append({"turn": s.turn, "role": "model", "kind": "answer", "text": summary})
        return SessionResult(results=results, summary=summary, model=self.name, transcript=s.transcript)

    async def reason(self, request, tools):
        """A judgement group in the multi-step setup: the playbook's tests are on
        each break; read the trades for the trade-level step, then recommend."""
        key = request.case_key
        items = request.group.get("items", [])
        found = []
        for it in items:
            tests = {t["id"]: t["status"] for t in it.get("tests") or []}
            ins = it["instrument"]
            if tests.get("FO-7") == "fail":
                found.append((ins, "ESCALATE", f"{ins}: FO-7 price = 0 in CATS; corporate action not evidenced (judgement, G)."))
            elif tests.get("FO-2") == "fail":
                found.append((ins, "DO_NOT_POST", f"{ins}: FO-2 failed, CATS opened at {it.get('fo_open_price')} against a close of "
                                                  f"{it.get('fo_prev_close_price')}; an FO price break (A), not posted."))
            else:
                ft = {t["trade_id"]: t for t in (await tools("cats.trades", {**key, "instrument": ins})).get("rows", [])}
                bt = {t["trade_id"]: t for t in (await tools("motif.trades", {**key, "instrument": ins})).get("rows", [])}
                diff = next(((tid, t["quantity"], bt[tid]["quantity"]) for tid, t in ft.items()
                             if tid in bt and bt[tid]["quantity"] != t["quantity"]), None)
                if diff:
                    found.append((ins, "POST", f"{ins}: trade {diff[0]} is {diff[2]:,} in MOTIF and {diff[1]:,} in CATS; "
                                               "a BO booking break (E)."))
                else:
                    found.append((ins, "ESCALATE", f"{ins}: FO, BO and trades agree; novel (H)."))
        verdicts = {v for _, v, _ in found}
        verdict = verdicts.pop() if len(verdicts) == 1 else "ESCALATE"
        text = " ".join(t for _, _, t in found)
        mixed = " The breaks in this group need different verdicts; decide them one by one." if len(found) > 1 and verdict == "ESCALATE" and len({v for _, v, _ in found}) > 1 else ""
        sections = {
            "root_cause": text,
            "hypotheses": "None beyond the root causes above." if verdict != "ESCALATE" else "See each break above.",
            "tests_not_performed": "Tests marked not run on the breaks (evidence or threshold missing) were not performed.",
            "verdict_reason": f"{VERDICT_WORDS[verdict]}.{mixed}",
            "remediation": "Engage the owner named on each break's category (market data, Operations, CATS support).",
            "preventative_control": "Propose MB Rec checks for the failing tests.",
            "end_state": "Open until each break's correction is confirmed; re-test BO + adjustments = FO.",
        }
        return ReasonResult(status="proposed" if verdict != "ESCALATE" else "escalated", comment=text,
                            reason=None if verdict != "ESCALATE" else "Judgement: SME review", model=self.name,
                            verdict=verdict if verdict in (request.verdicts or []) else None,
                            sections={k: v for k, v in sections.items() if any(x["id"] == k for x in request.sections)})
