"""Business requirements (BRD) → a draft capability manifest.

After aria-ai's `brd_to_pack`: one model turn, no tools, turns prose into a
manifest; the SAME validator the platform uses judges it; problems come back
to the author as a list, never as an exception; nothing goes live until an
owner other than the drafter approves it (capabilities.draft_new → approve).

The model is given what it needs to stay inside the platform: the manifest's
JSON schema, the core steps, the onboarded connector tools with their real
input schemas, and a worked example. The author is chosen with the reasoner
(HELIX_LLM_ADAPTER): `agent_sdk` uses the Claude Agent SDK; `stub` drafts from
templates so the flow works offline; a custom adapter may offer
`async draft_manifest(request) -> str`.
"""

import json
import re
from dataclasses import dataclass
from typing import Any

import yaml

from helix import gateway
from helix.config import settings
from helix.entitlement import Caller
from helix.manifest import Manifest, problems
from helix.workflow import catalogue

INSTRUCTIONS = """
You turn a business requirements document (BRD) into a Helix capability
manifest. Helix runs it as: load items from connector tools → compare or match
→ group → rules first, then the model with read-only tools → draft → validate
(every figure must trace to data) → human review → record → optional publish
(write-back after a second person releases it).

Rules:
- Use ONLY the connector tools listed below, by their exact qualified names.
  Write tools (access: write) may appear only as publish.tool.
- Steps must come from the core step list; validate, review and record are
  mandatory, in that order, and the run pauses before review (and publish).
- Expressions (in_scope, rules[].when) use item/group fields, `policy.<name>`,
  comparisons, and/or/not, and abs/min/max/len/round/startswith/contains only.
- Leave a policy value null rather than invent a threshold the BRD does not give.
- Owners: list the requesting user in owners.people.
- Write reasoning.skill as instructions to the model, grounded in the BRD.
Return the manifest as YAML in `yaml`, and every assumption you made in `assumptions`.
""".strip()

RESULT_SCHEMA = {
    "type": "object",
    "properties": {
        "yaml": {"type": "string"},
        "assumptions": {"type": "array", "items": {"type": "string"}},
    },
    "required": ["yaml"],
    "additionalProperties": False,
}


@dataclass(frozen=True)
class AuthoringRequest:
    brd: str
    requested_by: str
    context: dict          # schema, steps, tools, example — see build_context()


async def build_context() -> dict:
    reg = gateway.registry()
    tools = []
    for cid, spec in reg.connectors.items():
        for name, t in spec.tools.items():
            q = f"{cid}.{name}"
            tools.append({"name": q, "description": t.description, "access": t.access,
                          "data_scope_arg": t.scope.arg if t.scope else None,
                          "input_schema": await gateway.tool_schema(q)})
    example_path = settings().config_dir / "capabilities" / "fin-variance-commentary.yaml"
    return {
        "manifest_schema": Manifest.model_json_schema(by_alias=True),
        "core_steps": catalogue(),
        "connector_tools": tools,
        "example_manifest": example_path.read_text() if example_path.exists() else "",
    }


def _slug(text: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", text.lower()).strip("-")[:40] or "capability"


class TemplateAuthor:
    """Offline author: picks the closest built-in template and fills it from the
    BRD's title. Deterministic — for development and tests, not for real BRDs."""

    name = "template"

    async def draft_manifest(self, request: AuthoringRequest) -> tuple[str, list[str]]:
        text = request.brd.lower()
        title = next((ln.strip("# ").strip() for ln in request.brd.splitlines() if ln.strip()), "New capability")
        folder = settings().config_dir / "capabilities"
        recon = "bank" in text and ("ledger" in text or "reconcil" in text)
        base = yaml.safe_load((folder / ("recon-investigation.yaml" if recon else "fin-variance-commentary.yaml")).read_text())
        base["id"] = f"draft.{_slug(title)}"
        base["name"] = title[:80]
        lines = [ln for ln in request.brd.splitlines() if ln.strip()]
        body = " ".join(" ".join(lines[1:] if len(lines) > 1 else lines).split())
        base["description"] = body[:200]
        base["owners"] = {"people": [request.requested_by], "role": base["owners"].get("role"),
                          "four_eyes": True}
        assumptions = [f"Started from the {'cash reconciliation' if recon else 'variance commentary'} "
                       "template; review tools, rules and thresholds against the BRD."]
        return yaml.safe_dump(base, sort_keys=False), assumptions


class AgentSdkAuthor:
    """One Agent SDK turn, no tools, structured output {yaml, assumptions}."""

    name = "agent-sdk"

    def __init__(self, query_fn=None):
        from helix.llm_agent_sdk import ClaudeAgentSdkAdapter  # optional dependency
        self._sdk = ClaudeAgentSdkAdapter(query_fn=query_fn)

    async def draft_manifest(self, request: AuthoringRequest) -> tuple[str, list[str]]:
        from claude_agent_sdk import ClaudeAgentOptions

        from helix.llm_agent_sdk import _parse_any  # result → dict

        options = ClaudeAgentOptions(
            system_prompt=f"{INSTRUCTIONS}\n\nPlatform context:\n{json.dumps(request.context, default=str)}",
            tools=[], mcp_servers={}, strict_mcp_config=True, permission_mode="dontAsk",
            max_turns=2, model=self._sdk.model, effort=self._sdk.effort,
            output_format={"type": "json_schema", "schema": RESULT_SCHEMA},
        )
        prompt = f"Requested by: {request.requested_by}\n\nBRD:\n{request.brd}"
        out = _parse_any(await self._sdk._run(prompt, options))
        return out["yaml"], list(out.get("assumptions", []))


def author():
    from helix import llm

    choice = settings().llm_adapter
    if choice == "agent_sdk":
        return AgentSdkAuthor()
    if choice in ("stub", "none"):
        return TemplateAuthor()
    adapter = llm.llm()
    if hasattr(adapter, "draft_manifest"):
        return adapter
    return TemplateAuthor()


async def draft_from_brd(brd: str, caller: Caller, *, writer=None) -> dict[str, Any]:
    """Draft and judge; never raises on a bad draft — the author sees what to fix."""
    if not brd.strip():
        return {"yaml": "", "manifest": None, "problems": ["the BRD is empty"], "assumptions": []}
    writer = writer or author()
    request = AuthoringRequest(brd=brd, requested_by=caller.user_id, context=await build_context())
    try:
        text, assumptions = await writer.draft_manifest(request)
    except Exception as e:
        return {"yaml": "", "manifest": None, "assumptions": [], "author": getattr(writer, "name", "?"),
                "problems": [f"the author could not draft: {type(e).__name__}: {e}"]}
    return {**judge(text), "assumptions": assumptions, "author": getattr(writer, "name", "?")}


def judge(text: str) -> dict[str, Any]:
    """Parse and validate a manifest's YAML. The platform's own validator decides."""
    try:
        data = yaml.safe_load(text)
    except yaml.YAMLError as e:
        return {"yaml": text, "manifest": None, "problems": [f"not valid YAML: {e}"]}
    if not isinstance(data, dict):
        return {"yaml": text, "manifest": None, "problems": ["the draft is not a YAML mapping"]}
    try:
        m = Manifest.model_validate(data)
    except ValueError as e:
        errs = getattr(e, "errors", lambda: [])()
        found = [f"{'.'.join(str(p) for p in err['loc'])}: {err['msg']}" for err in errs] or [str(e)]
        return {"yaml": text, "manifest": None, "problems": found}
    return {"yaml": text, "manifest": m.model_dump(by_alias=True), "problems": problems(m)}


# ---------- guided authoring: answers → manifest, no model ----------

GUIDED_KINDS = {
    "investigate": "Investigate items another system already found (e.g. MB Rec's breaks)",
    "reconcile": "Match two systems and investigate what does not match",
    "commentary": "Compare actuals to a baseline and explain what is material",
    "review": "Review a list of items (attestations, exceptions)",
}


def available_modes() -> dict:
    """Which ways of authoring this deployment offers. Guided and templates
    always; drafting from a BRD with a model only when one is connected."""
    a = author()
    model = not isinstance(a, TemplateAuthor)
    return {"guided": True, "templates": True, "brd_model": model, "brd_author": a.name,
            "brd_note": None if model else
            "No model is connected here: a BRD only picks the nearest template. "
            "Answer the questions instead, or start from a template."}


async def _args_for(tool: str, key: list[str]) -> dict:
    """$case.<field> for every case-key field the tool takes."""
    try:
        props = (await gateway.tool_schema(tool)).get("properties", {})
    except Exception:
        props = {}
    return {k: f"$case.{k}" for k in key if not props or k in props}


async def guided(a: dict, caller: Caller) -> dict[str, Any]:
    """Build a manifest from a guided form's answers, then judge it with the
    platform's validator — exactly as a model's draft is judged."""
    problems_: list[str] = []
    name = (a.get("name") or "").strip() or "New capability"
    kind = a.get("kind") or "review"
    if kind not in GUIDED_KINDS:
        return {"yaml": "", "manifest": None, "assumptions": [], "author": "guided",
                "problems": [f"kind must be one of: {', '.join(GUIDED_KINDS)}"]}
    key = [k.strip() for k in (a.get("case_key") or []) if k and k.strip()] or ["entity", "date"]
    id_field = (a.get("id_field") or "").strip() or "id"
    amount = (a.get("amount_field") or "").strip() or None
    reviewers = [r for r in (a.get("reviewer_roles") or []) if r] or ["YOUR_REVIEWER_ROLE"]
    by_model = (a.get("decided_by") or "model_then_person") == "model_then_person"
    assumptions = []

    m: dict[str, Any] = {
        "id": (a.get("id") or "").strip() or f"draft.{_slug(name)}",
        "name": name[:80],
        "description": (a.get("description") or "").strip()[:300],
        "owners": {"people": [caller.user_id], "role": (a.get("owner_role") or None), "four_eyes": True},
        "case": {"label": a.get("case_label") or "Run", "item_label": a.get("item_label") or "Item",
                 "key": key, "subject": " · ".join(f"{{{k}}}" for k in key)},
        "items": {"id_field": id_field, "display": [f for f in (a.get("display") or []) if f]},
        "review": {"roles": reviewers},
    }
    scope = (a.get("scope_field") or "").strip()
    if scope:
        m["case"]["scopes"] = {scope: scope}
    if amount:
        m["items"]["amount_field"] = "difference" if kind == "reconcile" else (
            (a.get("compare_as") or "variance") if kind == "commentary" else amount)

    steps: list[str] = []
    if kind == "reconcile":
        left, right = a.get("left_tool"), a.get("right_tool")
        if not left or not right:
            problems_.append("a reconciliation needs both systems' tools")
        match_keys = [k for k in (a.get("match_keys") or []) if k] or [id_field]
        m["match"] = {"left": {"tool": left or "", "args": await _args_for(left, key) if left else {}},
                      "right": {"tool": right or "", "args": await _args_for(right, key) if right else {}},
                      "keys": match_keys, "amount_field": amount or "amount",
                      "tolerance": float(a.get("tolerance") or 0.01),
                      "left_label": a.get("left_label") or "left", "right_label": a.get("right_label") or "right"}
        m["items"]["id_field"] = match_keys[0] if len(match_keys) == 1 else id_field
        m["items"]["amount_field"] = "difference"
        steps.append("match")
    else:
        tool = a.get("source_tool")
        if not tool:
            problems_.append("say which tool the items come from")
        m["items"]["load"] = {"tool": tool or "", "args": await _args_for(tool, key) if tool else {}}
        steps.append("load")
        if kind == "commentary":
            measure, baseline = a.get("measure") or "actual", a.get("baseline") or "budget"
            m["compare"] = {"measure": measure, "baseline": baseline, "as": a.get("compare_as") or "variance"}
            steps.append("compare")

    materiality = a.get("materiality")
    if materiality not in (None, ""):
        m["policy"] = {"materiality": {"value": float(materiality), "unit": a.get("unit") or None}}
        if m["items"].get("amount_field"):
            m["items"]["in_scope"] = f"abs({m['items']['amount_field']}) >= policy.materiality"
    elif a.get("materiality_unconfirmed"):
        m["policy"] = {"materiality": {"value": None, "unit": a.get("unit") or None}}
        assumptions.append("Materiality is left unset until it is confirmed; nothing is filtered by it yet.")

    # steps v2: a few common building blocks, asked in plain words
    m["step_settings"] = {}
    if a.get("sample_size"):
        steps.append("pick")
        m["step_settings"]["pick"] = {"type": "sample", "label": "Sample",
                                      "with": {"method": "random", "size": int(a["sample_size"])}}
        assumptions.append(f"A random sample of {int(a['sample_size'])} is reviewed; the rest stay on the case, marked.")
    if a.get("clock_hours"):
        steps.append("sla")
        m["step_settings"]["sla"] = {"type": "clock", "label": "Service level", "with": {"clocks": [{
            "id": "sla", "label": f"Service level ({a['clock_hours']} h)", "starts": (a.get("clock_starts") or "case_opened"),
            "hours": float(a["clock_hours"]), "warn_before_hours": max(1.0, float(a["clock_hours"]) / 4)}]}}
    if a.get("authority_tool"):
        steps.append("authority")
        m["step_settings"]["authority"] = {"type": "dataset", "label": "Delegated authority", "with": {
            "name": "authority", "tool": a["authority_tool"], "args": await _args_for(a["authority_tool"], key)}}
        m["review"]["authority_dataset"] = "authority"
    elif a.get("two_approvers_over") not in (None, "") and m["items"].get("amount_field"):
        m["review"]["authority"] = [
            {"when": f"abs(total) >= {float(a['two_approvers_over'])}", "label": "two approvers",
             "approvals": 2, "lane": "enhanced", "bulk": False},
            {"label": "standard"}]
    reserved = [r for r in (a.get("reserved_roles") or []) if r]
    if reserved:
        m["boundaries"] = [{"when": (a.get("reserved_when") or "").strip() or None, "roles": reserved,
                            "model_may_propose": False, "reason": a.get("reserved_reason") or "a decision reserved for named people"}]
        if not (a.get("reserved_when") or "").strip():
            m["boundaries"][0]["when"] = "true"
            assumptions.append(f"Every decision is reserved for {', '.join(reserved)}; narrow it with a condition in Configure.")
    if not m["step_settings"]:
        del m["step_settings"]

    steps.append("group")
    m["group_by"] = [g for g in (a.get("group_by") or []) if g]
    steps += ["reason", "draft", "validate", "review", "record"]
    m["steps"] = steps
    pause = ["review"]
    if a.get("tollgate"):
        pause = ["reason", "review"]
        m["tollgates"] = {"reason": {"check": a.get("tollgate_check") or "Is the work so far right before the model is asked?"}}
    m["pause_before"] = pause

    m["reasoning"] = {"reasoner": "llm" if by_model else "none", "output": "commentary" if kind == "commentary" else "verdict",
                      "tools": [t for t in (a.get("model_tools") or []) if t]}
    if by_model:
        m["reasoning"]["skill"] = (a.get("instructions") or "").strip() or (
            f"You investigate {m['case']['item_label'].lower()}s for {name}. Use the tools to find why each "
            "group exists and what should happen next. Cite only figures from the tools or the items; "
            "escalate when the evidence does not explain it.")
        if not (a.get("instructions") or "").strip():
            assumptions.append("The model's instructions are a generic starting point; write your team's own in Configure.")
    else:
        assumptions.append("No model: what the rules cannot settle goes straight to the reviewers.")

    opens = a.get("opens") or "manual"
    if opens == "event":
        m["case"].update(opens_on="event", events=True, opens_as="helix-scheduler")
        if a.get("late_items"):
            m["case"]["late_items"] = "follow_up"
    elif opens == "schedule":
        m["case"].update(opens_on="schedule", schedule=a.get("schedule") or "30 6 * * 1-5",
                         schedule_keys=[dict(k) for k in (a.get("schedule_keys") or [])], opens_as="helix-scheduler")
        if not a.get("schedule_keys"):
            assumptions.append("Add the cases each scheduled run opens (Configure → Start: what a case is).")

    targets = [t for t in (a.get("ask_targets") or []) if t.get("name") and t.get("roles")]
    if targets:
        m["requests"] = {"targets": [{"id": _slug(t.get("id") or t["name"])[:40] or f"t{i}", "name": t["name"],
                                      "roles": list(t["roles"])} for i, t in enumerate(targets)]}
    questions = [q.strip() for q in (a.get("checklist") or []) if q and q.strip()]
    if questions:
        m["review"]["checklist"] = [{"id": f"q{i + 1}", "label": q, "required": True}
                                    for i, q in enumerate(questions)]
    if a.get("follow_through") and len(key) >= 2:
        m["follow_through"] = {"series": key[:-1], "order_by": key[-1]}
        assumptions.append(f"Follow-through: the same {', '.join(key[:-1])}, next {key[-1]}.")
    if a.get("retention_days"):
        m["retention"] = {"days": int(a["retention_days"])}
    if "YOUR_REVIEWER_ROLE" in reviewers:
        assumptions.append("Replace YOUR_REVIEWER_ROLE with the role that signs off.")

    text = yaml.safe_dump(m, sort_keys=False, allow_unicode=True)
    judged = judge(text)
    return {**judged, "problems": problems_ + judged["problems"], "assumptions": assumptions, "author": "guided"}
