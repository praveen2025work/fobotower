"""Data protection: what the model, the traces and the audit may see."""

import json
import re

import pytest

from agent_one_finance import llm
from agent_one_finance.governance import MASK, Protector
from agent_one_finance.llm import ReasonResult, StubLlm
from tests.agent_one_finance.conftest import CASH, RECON

KEY = {"entity": "UK01", "date": "2026-10-02"}
NAMES = ["ACME BANK", "GLOBEX", "INITECH", "UMBRELLA", "STARK"]


def test_masking_is_irreversible_and_pseudonyms_round_trip():
    p = Protector({"iban"}, {"counterparty"}, scope="case-1")
    data = {"rows": [{"counterparty": "GLOBEX", "iban": "GB00X", "amount": 12.5}]}
    seen = p.protect(data)
    row = seen["rows"][0]
    assert row["iban"] == MASK and row["amount"] == 12.5
    assert re.fullmatch(r"«COUNTERPARTY:[A-Z]{6}»", row["counterparty"])
    assert p.reveal(row["counterparty"]) == "GLOBEX"
    assert p.reveal(f"Chase {row['counterparty']} today") == "Chase GLOBEX today"
    assert "GB00X" not in json.dumps(p.reveal(seen))  # masked stays masked


def test_tokens_are_stable_within_a_case_and_differ_between_cases():
    a1, a2 = Protector(set(), {"counterparty"}, "a"), Protector(set(), {"counterparty"}, "a")
    b = Protector(set(), {"counterparty"}, "b")
    assert a1.token("counterparty", "GLOBEX") == a2.token("counterparty", "GLOBEX")
    assert a1.token("counterparty", "GLOBEX") != b.token("counterparty", "GLOBEX")


def test_tokens_never_look_like_figures():
    p = Protector(set(), {"counterparty"}, "c")
    assert not re.search(r"\d", p.token("counterparty", "ACME BANK 2026"))


class Capturing(StubLlm):
    """The stub model, recording exactly what it was given and what its tools returned."""

    name = "capturing"

    def __init__(self):
        self.requests, self.tool_results = [], []

    async def reason(self, request, tools):
        self.requests.append(request)

        async def watched(tool, args):
            result = await tools(tool, args)
            self.tool_results.append(result)
            return result

        res = await super().reason(request, watched)
        token = next(iter(request.group["group_key"].values()))
        return ReasonResult(status="proposed", model="stub",
                            comment=f"{res.comment} Chase {token} for settlement.")




async def test_the_model_never_sees_counterparty_names_or_accounts_but_tools_get_them(api):
    model = Capturing()
    llm._adapter = model
    res = await api.post(f"/api/capabilities/{RECON}/cases", json={"case_key": KEY, "team_group": CASH},
                         headers=api.as_user("dan"))
    case = res.json()
    assert case["status"] == "awaiting_review", res.text

    sent = json.dumps([r.group for r in model.requests] + model.tool_results, default=str, ensure_ascii=False)
    assert not any(name in sent for name in NAMES), "a real counterparty name reached the model"
    assert not re.search(r"GB\d{8}", sent), "an account number reached the model"
    assert "«COUNTERPARTY:" in sent

    # the connector was called with the real name (revealed by the gateway) ...
    model_calls = [c for c in case["tool_calls"] if c["requested_by"] == "llm"]
    assert model_calls and all(c["arguments"]["counterparty"] in NAMES for c in model_calls)
    # ... and the audit copy keeps real values minus the masked account numbers
    match_call = next(c for c in case["tool_calls"] if c["tool"] == "bank.statement")
    assert all(r["counterparty_account"] == MASK for r in match_call["result"]["rows"])

    # reviewers see real names: the model's tokens are re-identified
    for g in case["groups"]:
        comment = g["finding"]["comment"]
        assert "«" not in comment and g["group_key"]["counterparty"] in comment
        assert g["finding"]["status"] == "proposed"  # tokens did not trip validation


async def test_traces_carry_the_models_view_only(api, spans):
    spans.clear()
    llm._adapter = Capturing()
    await api.post(f"/api/capabilities/{RECON}/cases", json={"case_key": KEY, "team_group": CASH},
                   headers=api.as_user("dan"))
    payloads = [v for s in spans.get_finished_spans() if s.name == "mcp.call"
                for k, v in s.attributes.items() if k in ("input.value", "output.value")]
    assert payloads
    blob = " ".join(payloads)
    assert not any(name in blob for name in NAMES)
    assert "«COUNTERPARTY:" in blob and MASK in blob
