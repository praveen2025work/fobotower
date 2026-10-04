# FOBO on Helix

**Date:** 2026-10-04. The FOBO investigation console (`apps/backend/fobo`, `apps/console`)
is unchanged and keeps running. This page shows how the same behaviour is expressed on
Helix — as configuration of the shared reconciliation capability — so FOBO can move onto the
platform when the team is ready, and other rec groups get the same machinery.

**Where it lives:**

| What | Where |
|---|---|
| The FOBO rec group (CATS vs MOTIF) | `config/helix/groups/recon.investigation/cats-motif.yaml` |
| FOBO's reference lineage (books → desks → teams) | `config/helix/knowledge/fobo-reference.yaml` |
| Behaviour tests | `apps/backend/tests/helix/test_fobo_playbook.py` |

**How a FOBO run goes on Helix:**

```
match (CATS vs MOTIF) → enrich (break snapshots) → resolve (book → desk → team, as of the COB)
→ classify (C1–C6, all run, negatives kept) → group (category × side)
→ reason (verdict table | model + SME) → draft → validate (grounding) → review → record
```

## Parity

Status: **Same** = the same rule, now as Helix configuration ·
**Different** = the same purpose, reached another way · **Not yet**.

| FOBO | On Helix | Status |
|---|---|---|
| Playbook YAML (`config/playbook/fobo-cats-vs-motif.yaml`), owned by Product Control | `playbook:` in the rec group — versioned, four-eyes approved by the group's owners | **Same** |
| Six cause checks C1–C6 over dated snapshots; all run, negatives kept | `classify` step: `playbook.checks` over `motif.break_snapshots` joined by `enrich`; every result kept on the item | **Same** |
| Controller wording per cause (`cause_checks/reasons.py`) | `checks[].reason` | **Same** |
| Categories A–H, deterministic or judgement, with escalation team | `playbook.categories` (`determinism`, `escalate_to`) | **Same** |
| Default verdict by category × side | `playbook.verdicts` — deterministic categories with a proven side are settled by the table (`decided_by: playbook`) | **Same** |
| R2: an FO-origin cause never posts (enforced in code) | `playbook.guards` evaluated in code after the table *and* after the model | **Same** |
| R2: side UNKNOWN is not deterministic | unproven side → the model, marked `sme_review` | **Same** |
| P1: null threshold ⇒ "requires controller confirmation" | `policy` values left `null` + `playbook.verdict_policy` | **Same** |
| G/H → ESCALATE whichever side | a table that agrees for every side applies when the side is unknown | **Same** |
| Bitemporal lineage, `as_of` on every read (PRIME-MB-05 moved desk) | `resolve` step over the knowledge graph, `knowledge.as_of: cob` | **Same** |
| Priors from prior resolutions | approved decisions in the knowledge graph; same subject first, then shared entities (instrument, book) | **Different** — no 180-day lookback setting yet |
| Pattern groups | `group_by: [category, side]` | **Same** |
| Reasoner: none / session_service / direct | `HELIX_LLM_ADAPTER`: none / agent_sdk / stub (or your module) | **Different** — the Agent SDK in-process; no separate session service |
| Agent reads breaks over a per-session MCP endpoint | the model's tools are served in-process and every call goes through the Helix gateway (allow-list, scope, audit, protection) | **Different** |
| Grounding: every figure traces to a computed delta | `validate` gate: every figure traces to the run's data or tool results | **Same** |
| Idempotent controller decisions per pattern | idempotent decisions per group; bulk decide; required comments | **Same** |
| Reject-and-redraft cycles (`max_review_cycles`) | "Investigate again" with a reviewer note (`review.max_reinvestigations`) | **Different** |
| Workflow versions, draft → four-eyes approval, a run keeps its version | capability + group versions; each case keeps the exact merged manifest it ran on; `config_sync` for file changes | **Same** |
| A rec's investigation runs once, then replays its checkpoint | a case runs once per key (re-run makes attempt 2), off the request path; LangGraph checkpoints | **Same** |
| Chat drawer (ask about a rec) | "Ask about this case" — grounded, audited, protected | **Same** |
| Execution trace from checkpoints | "Run history" — each step, its time, the state "as it was" | **Same** |
| Board per COB, notification bell | Inbox and case lists per group; no notifications yet | **Not yet** (notifications) |
| Hours-saved tile | — | **Not yet** |
| Validation tests FO-1…FO-8, BO-1…BO-6 and FO-6 findings A/B/C | carried in the model's instructions (`reasoning.skill`); not yet structured checks with evidence requirements | **Not yet** (as structured tests) |
| `rank` step (order candidate causes) | the first positive check in playbook order is the cause | **Different** |

## Changing FOBO's rules on Helix

1. As a CATS vs MOTIF owner (frank, gina), open *Capabilities → Reconciliation investigation →
   Groups → CATS vs MOTIF*.
2. Edit the YAML — e.g. set `policy.materiality_threshold.value` once Product Control confirms
   it — and submit.
3. The other owner approves it.
4. New runs use the new version; past runs keep theirs.

To change a file in the repo and bring it into a running deployment:
`python -m helix.config_sync`, then approve the drafts.
