"""Data protection between bank data and the model (config/agent-one-finance/governance.yaml).

Two treatments, by field name (case-insensitive, at any depth):

  mask          irreversible: the value becomes ***MASKED*** wherever data
                leaves Agent One Finance's trust boundary — to the model, into traces,
                into the audit copy of a tool result.
  pseudonymize  reversible, per case: the value becomes a stable token like
                «COUNTERPARTY:QXKD». The model reasons and calls tools with
                tokens; the gateway turns tokens back into real values before
                a connector sees them, and re-tokenizes results on the way
                back. Reviewers see real values (comments are re-identified).

Adopted from aria-ai's eap governance (mask before prompt, audit, trace) and
extended with reversible tokens so masked identifiers stay usable as tool
arguments. Tokens use letters only, so they never look like a figure to
`validate`.
"""

import hashlib
import hmac
import os
import re
from dataclasses import dataclass, field
from fnmatch import fnmatch
from functools import lru_cache
from typing import Any, Literal

import yaml
from pydantic import BaseModel, ConfigDict, Field

from agent_one_finance.config import settings

MASK = "***MASKED***"
_TOKEN = re.compile(r"«([A-Z_]+):([A-Z]{4,})»")


class Strict(BaseModel):
    model_config = ConfigDict(extra="forbid")


class DataProtection(Strict):
    name: str
    applies_to_tools: list[str] = Field(default_factory=lambda: ["*"])  # fnmatch on "connector.tool"
    mask: list[str] = Field(default_factory=list)
    pseudonymize: list[str] = Field(default_factory=list)


class Governance(Strict):
    data_protection: list[DataProtection] = Field(default_factory=list)
    # What auto-instrumented spans (LangGraph state, Agent SDK messages) may carry:
    # masked = hide them, Agent One Finance's own spans carry protected payloads; full = no hiding.
    trace_payloads: Literal["masked", "full"] = "masked"


@lru_cache
def policy() -> Governance:
    path = settings().config_dir / "governance.yaml"
    if not path.exists():
        return Governance()
    return Governance.model_validate(yaml.safe_load(path.read_text()) or {})


def fields_for(tools) -> tuple[set[str], set[str]]:
    """(mask, pseudonymize) field names that apply to any of these tools."""
    mask, pseudo = set(), set()
    for rule in policy().data_protection:
        if any(fnmatch(t, pattern) for t in tools for pattern in rule.applies_to_tools):
            mask |= {f.lower() for f in rule.mask}
            pseudo |= {f.lower() for f in rule.pseudonymize}
    return mask, pseudo - mask


def _key() -> bytes:
    return (os.getenv("AOF_PSEUDONYM_KEY") or "aof-dev-only-key").encode()


def _letters(digest: bytes, n: int = 6) -> str:
    return "".join(chr(ord("A") + b % 26) for b in digest[:n])


@dataclass
class Protector:
    """One case's protection: the fields, and the token ↔ value map it has issued."""

    mask_fields: set[str] = field(default_factory=set)
    pseudo_fields: set[str] = field(default_factory=set)
    scope: str = ""                         # the case id: tokens differ between cases
    tokens: dict[str, str] = field(default_factory=dict)   # token -> real value

    @classmethod
    def for_tools(cls, tools, scope: str) -> "Protector":
        mask, pseudo = fields_for(tools)
        return cls(mask, pseudo, scope)

    @property
    def active(self) -> bool:
        return bool(self.mask_fields or self.pseudo_fields)

    def token(self, field_name: str, value: Any) -> str:
        digest = hmac.new(_key(), f"{self.scope}|{field_name}|{value}".encode(), hashlib.sha256).digest()
        t = f"«{re.sub(r'[^A-Z]', '_', field_name.upper())}:{_letters(digest)}»"
        self.tokens[t] = value
        return t

    def protect(self, data: Any, *, pseudonymize: bool = True) -> Any:
        """A copy with masked fields replaced and (optionally) pseudonymized fields tokenized."""
        def walk(v: Any, key: str | None = None) -> Any:
            k = key.lower() if key else None
            if k in self.mask_fields:
                return MASK
            if pseudonymize and k in self.pseudo_fields and isinstance(v, (str, int)) \
                    and not isinstance(v, bool):
                return self.token(k, v)
            if isinstance(v, dict):
                return {kk: walk(vv, kk) for kk, vv in v.items()}
            if isinstance(v, list):
                return [walk(x, key) for x in v]
            return v
        return walk(data)

    def protect_text(self, text: str, values: dict[str, Any]) -> str:
        """Tokenize known pseudonymized values that appear inside free text (labels)."""
        for k, v in values.items():
            if k.lower() in self.pseudo_fields and isinstance(v, str) and v:
                text = text.replace(v, self.token(k.lower(), v))
            if k.lower() in self.mask_fields and isinstance(v, str) and v:
                text = text.replace(v, MASK)
        return text

    def scrub(self, data: Any, known: list[dict[str, Any]]) -> Any:
        """Tokenize every protected value from `known` (group keys, items)
        wherever it appears in free text — labels, comments, questions."""
        pairs = {(k.lower(), v) for d in known for k, v in d.items()
                 if isinstance(v, str) and v and k.lower() in (self.pseudo_fields | self.mask_fields)}
        ordered = sorted(pairs, key=lambda kv: -len(kv[1]))     # longest first

        def text(t: str) -> str:
            for k, v in ordered:
                t = t.replace(v, self.token(k, v) if k in self.pseudo_fields else MASK)
            return t

        def walk(v: Any) -> Any:
            if isinstance(v, str):
                return text(v)
            if isinstance(v, dict):
                return {k: walk(x) for k, x in v.items()}
            if isinstance(v, list):
                return [walk(x) for x in v]
            return v
        return walk(data) if ordered else data

    def reveal(self, data: Any) -> Any:
        """Replace tokens with real values — in strings, dict values and lists."""
        if isinstance(data, str):
            whole = _TOKEN.fullmatch(data)
            if whole and data in self.tokens:
                return self.tokens[data]
            return _TOKEN.sub(lambda m: str(self.tokens.get(m.group(0), m.group(0))), data)
        if isinstance(data, dict):
            return {k: self.reveal(v) for k, v in data.items()}
        if isinstance(data, list):
            return [self.reveal(v) for v in data]
        return data


def configure_trace_hiding() -> None:
    """Hide payloads in auto-instrumented spans unless governance says `full`.
    OpenInference instrumentors read these at instrumentation time."""
    if policy().trace_payloads == "masked":
        os.environ.setdefault("OPENINFERENCE_HIDE_INPUTS", "true")
        os.environ.setdefault("OPENINFERENCE_HIDE_OUTPUTS", "true")
        os.environ.setdefault("OPENINFERENCE_HIDE_LLM_INVOCATION_PARAMETERS", "false")
