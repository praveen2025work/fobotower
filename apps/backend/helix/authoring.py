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
