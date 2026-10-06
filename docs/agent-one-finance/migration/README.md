# FOBO → Agent One Finance change guide (for the office)

**Date:** 2026-10-04 · **For:** the engineer moving FOBO onto Agent One Finance in the office, and the
office Claude Code that does the conversion with them.

**Where you are.** In the office, the old FOBO app has already been converted to run on the
office agent platform ("Agent One"): the Claude Agent SDK for model calls, office MCP servers
for CATS and MOTIF, and Phoenix for traces. FOBO is still its own application, with its own
orchestrator, rules code, tools, screens and database.

**Where you are going.** FOBO stops being an application. It becomes **one rec group on Agent One Finance's
shared reconciliation capability**, at the accounting-platform level: the same machinery every
accounting team uses (Prime, Rates, cash, accruals and so on). FOBO's rules move from code
into configuration. Agent One's Agent SDK wrapper, MCP servers and Phoenix setup are kept and
plugged into Agent One Finance. Everything FOBO-specific that Agent One Finance already does is retired.

**The rule for the whole migration: the controller sees the same answer.** For every break,
the category, side and verdict must match the old run. The parity script in Phase 5 proves
this. Anything that would change an answer is stopped, written down and decided by Product
Control. It is never "fixed" quietly.

**How to use this guide with office Claude Code:**

1. Copy [`office-claude/fobo-to-aof/SKILL.md`](office-claude/fobo-to-aof/SKILL.md) into your office repo as
   `.claude/skills/fobo-to-aof/SKILL.md`.
2. Copy this folder (`docs/agent-one-finance/migration/`) into the office repo too, so the skill can read it.
3. Start a session with the prompt in [§9](#9-the-prompt-to-start-office-claude). Claude works
   one phase at a time and stops for your sign-off between phases.

**Already have an office copy under the old name, Helix?** Upgrade it first with the <!-- aof-convert: keep -->
[`upgrade-to-aof`](office-claude/upgrade-to-aof/SKILL.md) skill. It renames the copy, brings in
everything in [`whats-new.md`](whats-new.md), and keeps the office's own changes. See
[`office-claude/README.md`](office-claude/README.md) to choose.

---

## 1. Before and after

```
BEFORE — FOBO on Agent One (one app, one team)

  FOBO orchestrator (LangGraph)                         FOBO console
   resolve → gather → group → reason → rank → draft      board, detail, chat,
   → validate → review → record                          workflow tab
     │   cause checks C1–C6, verdict table, R2, P1  ← Python code
     │   playbook YAML + workflow YAML (own versioning)
     ├── reasoner: Agent One session (start/poll), one session per rec,
     │   fobo_* MCP tools (list_breaks, break_detail, similar_breaks, …)
     └── CATS / MOTIF via office MCP servers           Postgres (fobo_* tables)

AFTER — FOBO as a rec group on Agent One Finance (one platform, every accounting team)

  Agent One Finance web (inbox, case workspace, review, release)    ← all teams
  Agent One Finance API ── capability break.investigation (shared engine, mandatory gates)
                 └── group fobo-prime (Prime), a Rates group, …  ← FOBO is YAML here
       steps: load (MB Rec's breaks) → enrich → resolve → classify (timing first) → group
              → tollgate (controller + the desk's input) → reason → draft
              → validate* → review* → record*         (* gates cannot be removed)
       ├── llm: Agent One's Agent SDK wrapper as the Agent One Finance LLM adapter (one call per group)
       ├── gateway: allow-list, data scope, audit row, masking → office MCP servers
       ├── knowledge graph: book → desk → team as of COB; approved decisions as priors
       └── Phoenix: one trace per case run
```

## 2. What moves where

Find each row's "Agent One" column in your office code during Phase 0. The paths given are where
they sit in this repo's FOBO (`apps/backend/fobo`). The Agent One conversion probably kept
similar names.

| FOBO concept | FOBO / Agent One (typical place) | Agent One Finance target | How it moves |
|---|---|---|---|
| Rec run (book × COB) | `investigation/agent_run.py`, `state.py` | a **case** keyed `[book, cob]` | `set.case` in the group file |
| The breaks (MB Rec has already reconciled CATS to MOTIF) | `steps/gather.py` reads them from MB Rec | `load` from `mbrec.breaks` on the **Break investigation** capability — no re-matching (see [Configure it](../guide/configure-fobo-mb-rec.md)) | config |
| Dated FO/BO snapshots | `gather.py` (`break_snapshots`) | `enrich` with `motif.break_snapshots` | config |
| Book → desk → team as of COB | `steps/resolve.py`, `knowledge_graph/ontology.py` | `resolve` + `config/agent-one-finance/knowledge/fobo-reference.yaml`, `knowledge.as_of: cob` | reference YAML |
| Cause checks C1–C6 (all run, negatives kept) | `cause_checks/checks.py` + `reasons.py` | `playbook.checks[]` (`when`, `category`, `side`, `reason`) | **code → expressions** |
| Validation tests FO-1…8, BO-1…6 | playbook YAML `tests:` | `playbook.tests[]` (`fails_when`, `needs`, `policy`, `blocks_post`) | YAML → YAML |
| FO-6 findings A/B/C | playbook YAML | `playbook.findings[]` | YAML → YAML |
| Categories A–H and escalation team | playbook YAML, `contracts.CATEGORY_NAMES` | `playbook.categories` | YAML → YAML |
| Verdict table category × side | `reasoning/determinism.py` | `playbook.verdicts` | **code → table** |
| R2: an FO cause never posts | `reasoning/guards.py` | `playbook.guards[]` (applied after the table *and* after the model) | **code → guard** |
| P1: unset threshold ⇒ confirm | `policy:` nulls + `determinism.py` | `policy` nulls + `confirm_verdicts` + `verdict_policy` + `review.confirm` | config |
| Pattern groups | `steps/group.py` | `group_by: [category, side]`, `group_label` | config |
| Priors (180-day lookback) | `fobo_similar_breaks`, `gather.py` | `knowledge.priors_lookback_days: 180` → `group.priors` | config |
| Reasoner (session start/poll per rec) | `reasoning/adapters/session_service.py` or Agent One equivalent | **LLM adapter**, one `reason()` per group | **keep Agent One's SDK call, re-shape it** (§4) |
| fobo_* MCP tools for the agent | `mcp_server/tools.py` | not needed: see §4.2 | retire |
| Agent skill (`skills/fobo-investigation/SKILL.md`) | Agent One plugin/skill | `reasoning.skill` (+ `reasoning.specialists`) | text, trimmed (§4.3) |
| Booking-events trawl | inside the agent session | `reasoning.tools: [motif.booking_events]` + specialist `booking-events` | config |
| Grounding (every figure traces) | `steps/validate.py`, `grounding/recorder.py` | `validate` gate (mandatory) | built in |
| Draft (four-part analysis) | `steps/draft.py` | `draft` step + playbook `comment` template | config |
| `rank` step | `steps/rank.py` | first positive check in playbook order is the cause | **behaviour note** (§6) |
| Controller sign-off | console decisions, `web/decisions.py` | `review` gate: roles, `require_comment`, `bulk_exclude`, `confirm` | config |
| Record → tomorrow's priors | `steps/record.py` | `record` gate → knowledge graph | built in |
| Reject-and-redraft (`max_review_cycles`) | workflow settings | "Investigate again" with a note (`review.max_reinvestigations`) | **behaviour note** (§6) |
| Playbook / workflow versions, four-eyes | `investigation/versions.py`, workflow tab | group and capability versions, four-eyes, a case keeps its version | built in |
| 11:00 run per COB | scheduler / Agent One trigger | `case.opens_on: schedule`, `schedule_keys`, `events: true` | config |
| Rec deadline | — | `case.due: {from: cob, business_days: 1, at: "11:00"}` | config |
| Fix upstream → owning team | named in the analysis | `escalation` raises a ticket after the decision | config (needs a ticketing connector) |
| Board, detail, chat, trace, hours saved | `apps/console`, `console_views/*`, `reports/*` | Agent One Finance inbox, case workspace, "Ask about this case", run history, Overview | built in |
| Phoenix tracing | Agent One's setup | `PHOENIX_COLLECTOR_ENDPOINT` or `AOF_TRACING_SETUP=pkg.mod:fn` | env |
| Users, roles, books visible | FOBO auth | `AOF_ENTITLEMENT_URL` (roles + `book` data scope), `AOF_IDENTITY_HEADER` | env |

**Reference implementation.** The Prime group, already converted and tested:
`config/agent-one-finance/groups/break.investigation/fobo-prime.yaml` (MB Rec's breaks, timing checks,
the tollgate). The older `recon.investigation/cats-motif.yaml` and `cats-motif-rates.yaml` match
CATS to MOTIF in Agent One Finance itself. Use them only where no system has reconciled already. Their
playbook is the same.
Behaviour tests: `apps/backend/tests/agent_one_finance/test_fobo_playbook.py`. Line-by-line parity:
[`../fobo-on-agent-one-finance.md`](../fobo-on-agent-one-finance.md).

## 3. What you keep from Agent One, and what you retire

**Keep and plug in. These are the office's, and Agent One Finance should not rebuild them.**

| Agent One piece | Plug into Agent One Finance as |
|---|---|
| The Agent SDK wrapper (auth, model routing, gateway URL) | the body of `_run` in `agent_one_finance/llm_agent_sdk.py`, or your own adapter selected with `AOF_LLM_ADAPTER=pkg.mod:obj` |
| CATS / MOTIF / ticketing MCP servers | entries in `config/agent-one-finance/connectors.yaml` (`transport: http`, `url`, `headers_env`). With ids `cats`, `motif` and `ticketing` the group file works unchanged. Otherwise, change the names in the group file to match (config only) |
| RAG / data explorer servers | connectors too, if the skill needs them |
| Phoenix setup | `AOF_TRACING_SETUP=pkg.mod:fn`, or just the endpoint |
| PreToolUse / PostToolUse hooks | keep them as a second line of defence, wired to the same allow-list as the gateway |
| The investigation skill text | `reasoning.skill`, trimmed (§4.3) |

**Retire once parity holds (Phase 6).** Do not delete anything before then.

- The FOBO orchestrator, its steps and the step registry.
- The rules code: cause checks, determinism / verdict table, guards. These are now config.
- The fobo_* MCP server and its tools.
- The session-service reasoner (start/poll).
- FOBO's own playbook and workflow versioning, the workflow tab and the YAML loader CLI.
- The FOBO console. Users move to the Agent One Finance web app.
- FOBO's tables. Keep them read-only for the records retention period; do not drop them.

**Never** load Agent One's MCP servers straight into the Agent SDK inside Agent One Finance. A tool the model
reaches outside the gateway skips the allow-list, the book scope check and the audit row. The
adapter sets `strict_mcp_config=True` for this reason.

## 4. The model side: from one session per rec to one call per group

This is the only real code change, and it is small.

### 4.1 The contract

Agent One's FOBO reasoner was **rec-level and asynchronous**. It started one agent session for
the whole run and polled it. It returned a `RecVerdict` with one verdict per pattern plus
exceptions.

Agent One Finance is **group-level and awaited**. It makes one `reason()` call per proposal group, runs
groups in parallel, and checkpoints and resumes the run itself:

```python
class LlmAdapter(Protocol):
    name: str
    async def reason(self, request: ReasonRequest, tools: ToolInvoker) -> ReasonResult: ...
# ReasonRequest: case_key, skill, group {label, group_key, items, priors},
#                allowed_tools, verdicts, specialists, reviewer_note, previous_finding
# ReasonResult:  status proposed|escalated, comment, reason, verdict, model, usage
```

**Do this.** Start from `agent_one_finance/llm_agent_sdk.py`, which already implements the contract on the
Agent SDK, and replace only `_run` with Agent One's way of calling the SDK (auth, model routing,
internal endpoint). If Agent One exposes only a start/poll session service, write a thin adapter
that starts a session for the group and awaits it. Do not reintroduce start/poll in the engine.

### 4.2 The fobo_* tools are not needed

| fobo_* tool | Why Agent One Finance does not need it |
|---|---|
| `fobo_list_breaks`, `fobo_break_detail` | every break in the group is in the prompt (`group.items`, full rows, with enrich, resolve, classify and test results on each) |
| `fobo_list_tests`, `fobo_evidence_required`, `fobo_required_on_fail`, `fobo_unset_policies` | the playbook already ran: each item carries its check results, test results (pass / fail / not run, and why) and the P1 flag |
| `fobo_book_context` | the `resolve` step put `owner_desk` and `owner_team` on each item, as of the COB |
| `fobo_similar_breaks` | `group.priors`: approved decisions on the same subject, then shared instrument or book, within 180 days |

The model's only tool is `motif.booking_events`, through the gateway. It can also hand that
work to the `booking-events` specialist (an Agent SDK subagent).

### 4.3 The skill text

Keep the investigation method from Agent One's skill: hypotheses, never assume FO is right,
exceptions, and "recommend, don't decide". Remove anything that is now done before the model
sees the group:

- how to call the fobo_* tools;
- the rec / patterns / `already_established` input description (the input is now one group);
- the §12 output format (Agent One Finance asks for a structured `{status, comment, verdict, reason}`, and
  its own output rules are appended).

The result is short, like the `reasoning.skill` in `cats-motif.yaml`.

**`CORRECT_AND_REPOST`.** The old contract allowed this verdict and the Agent One Finance FOBO groups do not
list it. If Agent One's runs ever produce it, Product Control decides how it maps. Do not add
it silently.

## 5. Behaviour that must not change

Each rule below has an Agent One Finance test that proves it. Run them after every change to the group file.

| Rule | Proven by (`apps/backend/tests/agent_one_finance/`) |
|---|---|
| All six checks run on every break; negatives are kept | `test_fobo_playbook.py` |
| Deterministic category + proven side → settled by the table (`decided_by: playbook`), no model | `test_fobo_playbook.py` |
| R2: an FO cause never posts, after the table *and* after the model | `test_fobo_playbook.py` |
| R2: side UNKNOWN is never deterministic → model + SME | `test_fobo_playbook.py` |
| P1: a POST under an unset threshold needs a tick and a comment; "Approve all" skips it | `test_fobo_playbook.py`, `test_review_features.py` |
| G and H always escalate | `test_fobo_playbook.py` |
| FO-1/2/4/7 failures hold a POST; a test with missing evidence or an unset threshold is "not run", never passed | `test_fobo_playbook.py` |
| Desk lineage as of the COB (PRIME-MB-05 moved desk on 2026-07-01) | `test_knowledge.py`, `test_fobo_playbook.py` |
| Priors from the last 180 days | `test_knowledge.py` |
| Every figure the model states traces to data or a tool result | `test_reasoning.py` |
| A run keeps the rules version it started on; rule changes need a second owner | `test_groups.py`, `test_capability_versions.py` |
| Prime users cannot see Rates books, and the reverse | `test_fobo_playbook.py` |

```bash
cd apps/backend && .venv/bin/python -m pytest -q tests/agent_one_finance/test_fobo_playbook.py tests/agent_one_finance/test_knowledge.py \
  tests/agent_one_finance/test_reasoning.py tests/agent_one_finance/test_groups.py tests/agent_one_finance/test_review_features.py
```

## 6. Known, accepted differences

These change *how* work flows, not the category, side or verdict on a break. Tell the
controllers before go-live.

| Old | Agent One Finance | Effect on users |
|---|---|---|
| `rank` orders candidate causes | the first positive check in playbook order is the cause | the same in practice, because the playbook orders checks by precedence. Confirm with Product Control |
| reject-and-redraft cycles | "Investigate again" with a note, per group | the reviewer sends back one group, not the whole run |
| one agent session per rec | one model call per group, in parallel | faster; cost and trace per group |
| FOBO console | Agent One Finance web | new screens, same information. See the [user guide](../guide/user-guide.md) |
| owner team named in the analysis | also a ticket for that team (if `escalation` is configured) | less copy-paste |

## 7. Phases

Each phase ends with a check and your sign-off. Office Claude stops at every one.

| # | Phase | Done when |
|---|---|---|
| 0 | **Inventory.** Map Agent One's FOBO code and config to every row of §2. Record the actual policy values, schedule, books, roles, MCP server URLs and tool names. Write `MIGRATION_INVENTORY.md` | every §2 row has an office location or "not present"; open questions are listed |
| 1 | **Bring Agent One Finance in.** Add `apps/backend/agent_one_finance`, its migrations, `apps/web`, `config/agent-one-finance` from `praveen2025work/fobotower` main. Give it its own database (`AOF_DATABASE_URL`). Run `alembic upgrade head` | the API starts with the stub model; `pytest tests/agent_one_finance` is green |
| 2 | **Connectors.** Point `cats`, `motif` (and `ticketing`, `documents` if used) at the office MCP servers. Start from `connectors.office.example.yaml`; secrets go in env only | `scripts/aof_office_smoke.py --user <id>` passes database, entitlements, connectors |
| 3 | **Rules as config.** Copy `break.investigation/fobo-prime.yaml` and set the office values from the inventory: books, schedule, policy values (nulls stay null), tests, categories, verdicts, guards, roles. Copy `fobo-reference.yaml` with the office's book → desk → team lineage. One file per FOBO rec group (Prime, Rates, …). Anything the YAML cannot express goes to `MIGRATION_GAPS.md`, not into engine code | `python -m agent_one_finance.config_sync` creates drafts, a second owner approves, and §5 tests pass |
| 4 | **Model.** Plug Agent One's SDK call into the adapter (§4.1). Trim the skill (§4.3). Set `AOF_LLM_ADAPTER`, `PHOENIX_COLLECTOR_ENDPOINT`, `AOF_ENTITLEMENT_URL`, `AOF_IDENTITY_HEADER`, `AOF_TRUSTED_PROXY_SECRET` | smoke test with `--case break.investigation --group fobo-prime --key book=… --key cob=…` passes, and the trace appears in Phoenix |
| 5 | **Parallel run.** Run each book's COB in both systems for an agreed period (suggested: 10 business days, every book). Compare with the parity script (below). Log every difference in `PARITY_LOG.md` with a cause and a decision | zero unexplained differences across the period; Product Control signs off |
| 6 | **Cut-over and retire.** Switch the 11:00 schedule to Agent One Finance, turn off the FOBO trigger, and move users to Agent One Finance web. Retire the §3 list after one clean month-end. Keep FOBO tables read-only | Agent One Finance is the only system writing; rollback plan tested once |

**Parity script** (in this repo: `apps/backend/scripts/fobo_aof_parity.py`):

```bash
# Old: export the run's breaks as CSV or JSON (columns: instrument, category, side, verdict)
# Agent One Finance: the case for the same book and COB
.venv/bin/python scripts/fobo_aof_parity.py --old old_PRIME-MB-01_2026-09-30.csv \
    --api https://aof.internal.example --case-id <case_id> --user <your id>
# Different column names in the old export:
#   --old-columns "id=break_ref,category=root_cause_category,side=origin,verdict=recommendation"
```

The script prints each break where category, side or verdict differ, or that only one system
has. It exits 0 only when everything agrees. When the model is involved, compare the
deterministic breaks first (Agent One Finance finding `decided_by: playbook`). Model-decided verdicts can
legitimately vary between two model runs, so review those by reading, not by diff.

## 8. Rollback

Until Phase 6 is signed off, FOBO on Agent One stays the system of record. Rollback means
turning off the Agent One Finance group (the off switch in Operations, or `case.opens_on: manual`) and
carrying on. After cut-over, keep the Agent One deployment able to start for one month-end.
Rollback is then: Agent One Finance off switch, Agent One trigger on, and tell the controllers.

## 9. The prompt to start office Claude

Paste this into Claude Code in the office repo, after copying the skill (top of this page):

```text
Use the fobo-to-aof skill. We are moving our FOBO on Agent One to Agent One Finance: FOBO becomes
groups of Agent One Finance's break.investigation capability, on MB Rec's breaks. The change guide
is docs/agent-one-finance/migration/README.md.

Start with Phase 0 only: inventory our FOBO code and config against every row of the
guide's §2 table and write MIGRATION_INVENTORY.md. Do not change any code yet. List
every policy value, book, schedule, role, MCP server and tool name you find, with the
file and line. Then stop and show me the open questions.
```

Then, phase by phase: "Phase 1 approved, continue with Phase 1", and so on.

## 10. Sign-off checklist

- [ ] Inventory complete; open questions answered by Product Control
- [ ] Agent One Finance tests green in the office (`pytest tests/agent_one_finance`)
- [ ] Office smoke test passes, including one real case and its Phoenix trace
- [ ] Each FOBO rec group file approved by two owners
- [ ] Policy thresholds: the same values as FOBO (nulls stay null, P1)
- [ ] Parity: zero unexplained differences over the parallel-run period, for every book
- [ ] `MIGRATION_GAPS.md` empty, or each gap accepted by Product Control
- [ ] Controllers trained on Agent One Finance web (user guide); delegation set up for leave
- [ ] Rollback tested once
- [ ] FOBO trigger off; FOBO tables read-only; retirement list done after one month-end
