---
name: fobo-to-aof
description: Move FOBO (CATS vs MOTIF break investigation, already running on the office Agent One / Claude Agent SDK platform) onto Agent One Finance as groups of the shared break.investigation capability (breaks MB Rec has already reconciled). Use when asked to inventory, convert, configure, parity-test, cut over or retire FOBO for Agent One Finance. Works phase by phase from docs/agent-one-finance/migration/README.md and stops for sign-off after each phase.
---

# FOBO → Agent One Finance migration

You are converting this repository's FOBO, which runs on Agent One, so that FOBO runs as
**configuration on Agent One Finance**: one group file per FOBO rec group (Prime, Rates, …) on Agent One Finance's
`break.investigation` capability, which reads the breaks MB Rec has already reconciled. The Agent SDK call, MCP servers and Phoenix setup that
Agent One already has are plugged into Agent One Finance. They are not rebuilt.

**Read first, every session:**

1. `docs/agent-one-finance/migration/README.md` — the change guide: the mapping table (§2), what to keep
   or retire (§3), the model contract (§4), invariants (§5), accepted differences (§6),
   phases (§7).
2. `docs/agent-one-finance/fobo-on-agent-one-finance.md` — the line-by-line parity table.
3. The reference conversion: `config/agent-one-finance/capabilities/break-investigation.yaml` and
   `config/agent-one-finance/groups/break.investigation/fobo-prime.yaml`. These read MB Rec's breaks,
   with timing checks and a tollgate. See `docs/agent-one-finance/guide/configure-fobo-mb-rec.md`.
   FOBO never re-matches CATS to MOTIF; that is MB Rec's job.

If any of these files is missing, stop. Ask the user to copy them in from
`praveen2025work/fobotower` (main).

## Rules that override everything else

1. **The controller sees the same answer.** For every break, the category, side and verdict
   must match FOBO. If something would change an answer, do not change it. Write it in
   `MIGRATION_GAPS.md` (what, where, the old behaviour, the options) and ask.
2. **No FOBO code in the Agent One Finance engine.** FOBO is configuration: the group YAML, reference YAML
   and connectors. Do not edit `aof/steps.py`, `workflow.py`, `manifest.py`, `gateway.py`
   or the gates to fit a FOBO quirk. If the YAML cannot express a rule, that is a gap
   (rule 1). The only code you write is the LLM adapter's `_run` (§4.1 of the guide), plus
   connector or entitlement wiring if the office needs it.
3. **Never invent a threshold** (P1). A policy value that FOBO has as null stays null. Copy
   real values exactly, with their unit and source file and line.
4. **Keep the safety rules:**
   - R2: an FO-origin cause never posts. Keep it as a `playbook.guards` entry.
   - Side UNKNOWN is never deterministic.
   - G and H escalate.
   - FO-1/2/4/7 failures hold a POST.
   - Missing evidence or an unset threshold means "not run", never a pass.
   - Gates validate, review and record stay.
5. **Every model tool goes through the Agent One Finance gateway.** Onboard the office MCP servers as
   connectors in `config/agent-one-finance/connectors.yaml`. Never pass them straight to the Agent SDK
   (`mcp_servers`), and keep `strict_mcp_config=True` and `tools=[]`.
6. **No secrets in files.** Use `headers_env` and the environment.
7. **Delete nothing before Phase 6 is signed off.** FOBO stays the system of record until then.
8. **One phase per turn.** Finish the phase, run its check, report, and stop. Wait until the
   user says the phase is approved.
9. Use the repository's commit conventions. Commit each phase separately, with a message
   that names the phase.

## Phase 0 — Inventory (read only)

Find where each row of the guide's §2 table lives in *this* repository. Useful searches:

| Looking for | Search for |
|---|---|
| Cause checks C1–C6 | `C1`, `cutoff`, `mapping_present`, `dataset_id`, `symdiff`, `CandidateCause` |
| Verdict table, R2, P1 | `DO_NOT_POST`, `ESCALATE`, `CORRECT_AND_REPOST`, `side == "FO"`, `requires_confirmation`, `materiality_threshold` |
| Playbook / workflow config | `fobo-cats-vs-motif`, `playbook`, `effective_from`, `pause_before`, `steps:` |
| Agent call | `claude_agent_sdk`, `query(`, `ClaudeAgentOptions`, `session`, `start(`, `poll(` |
| Agent tools | `fobo_list_breaks`, `fobo_break_detail`, `fobo_similar_breaks`, `@tool`, `create_sdk_mcp_server` |
| MCP servers | `mcp`, `url`, `CATS`, `MOTIF`, `booking_events`, `break_snapshots`, `positions` |
| Skill text | `SKILL.md`, `system_prompt`, `Product Controller` |
| Schedule, books, roles | `cron`, `11:00`, `PRIME-`, `RATES-`, `FOBO_CONTROLLER`, `role` |
| Lineage | `belongs_to`, `escalates_to`, `desk`, `as_of`, `valid_from` |
| Tracing | `phoenix`, `opentelemetry`, `openinference` |

Write `MIGRATION_INVENTORY.md` with:

- **One table, one row per §2 row:** FOBO concept · file:line in this repo · current value or
  behaviour · Agent One Finance target · notes. Write "not present" where Agent One has no such thing.
- **Values:**
  - every policy threshold (value, unit, file:line);
  - every book and rec group;
  - the schedule and COB rule;
  - reviewer and owner roles;
  - escalation teams.
- **Connectors:** each MCP server's URL, auth header env var, and each tool's name, arguments
  and which argument carries the book (for the data scope).
- **Agent:**
  - how the SDK is called: model, auth, routing, hooks, budget;
  - rec-level or pattern-level;
  - the output contract and verdicts used.
- **Differences from this repo's reference FOBO.** Anything Agent One changed while
  converting: extra checks, different verdicts, a different grouping.
- **Open questions** for Product Control, numbered.

Check: every §2 row is filled in. Stop and show the open questions.

## Phase 1 — Bring Agent One Finance in

1. Add from `praveen2025work/fobotower` main:
   - `apps/backend/agent_one_finance/` with its migrations and `pyproject` dependencies;
   - `apps/backend/scripts/aof_office_smoke.py` and `fobo_aof_parity.py`;
   - `apps/backend/tests/agent_one_finance/`;
   - `apps/web/`;
   - `config/agent-one-finance/`.

   Do not overwrite this repo's FOBO files.
2. Give Agent One Finance its own database (`AOF_DATABASE_URL`). Run `alembic upgrade head`.
3. Run with the defaults (`AOF_LLM_ADAPTER=stub`, dev users):

   ```
   pytest -q tests/agent_one_finance
   uvicorn agent_one_finance.web.main:app --port 8300
   ```

Check: tests green, and the API starts. Report the test counts.

## Phase 2 — Connectors

1. Copy `config/agent-one-finance/connectors.office.example.yaml` entries into `connectors.yaml` for
   `cats`, `motif` (and `ticketing`, `documents` and RAG if used).
2. Fill each entry with the inventory's URLs and env var names.
3. Prefer the connector ids the group file uses: `cats`, `motif`, `ticketing`. Tool names
   must be the office server's real tool names; Agent One Finance calls them as written.
   - If they differ from the reference (`positions`, `break_snapshots`, `booking_events`,
     `create_ticket`), use the office names in `connectors.yaml` and in the group file
     (`match`, `enrich`, `reasoning.tools`, `escalation.tool`). Both are config.
   - If a tool's arguments or result fields differ (e.g. `book_id` not `book`), set the
     group's `args`, `keys` and field names to match. If the fields the playbook needs are
     not returned at all, that is a gap.
4. Set each tool's `scope` to the argument that carries the book.

Check: `python scripts/aof_office_smoke.py --user <real id>` passes database,
entitlements and connectors.

## Phase 3 — Rules as configuration

For each FOBO rec group in the inventory:

1. Copy `break.investigation/fobo-prime.yaml` to a new group file and set the office values:
   - `items.load` (the MB Rec breaks tool and its arguments), `due`, how cases open
     (MB Rec's event);
   - the timing checks (`AGED`, `TIMING`) as the office defines them;
   - `policy` (nulls stay null);
   - `playbook` checks, tests, findings, categories, verdicts, guards;
   - `review.roles`, owners.
2. Translate any check that was code into a `when` expression. See the developer guide §8 for
   expressions: `symdiff`, `len`, `abs` and comparisons.
   - Write one line per check in the inventory showing the code and the expression side by
     side.
   - If an expression cannot express it, that is a gap.
3. Put the office's book → desk → team lineage, with dates, in
   `config/agent-one-finance/knowledge/<name>.yaml`, in the shape of `fobo-reference.yaml`.
4. Validate the files:
   - run `python -m agent_one_finance.config_sync` to create drafts;
   - have a second owner approve them in Authoring.
5. Run the invariant tests (guide §5). Add a test for each office-specific rule, modelled on
   `tests/agent_one_finance/test_fobo_playbook.py`.

Check: drafts approved, §5 tests and new tests green.

## Phase 4 — The model

1. Start from `aof/llm_agent_sdk.py`. Replace only `_run` with Agent One's way of calling
   the SDK (auth, routing, internal endpoint, budget). Keep the contract:
   `name` and `async reason(request, tools) -> ReasonResult`.
   - If Agent One only offers start/poll sessions, start one per group and await it inside
     `reason()`.
   - Select it with `AOF_LLM_ADAPTER=agent_sdk` (or `pkg.mod:obj`).
2. Bring over Agent One's PreToolUse/PostToolUse hooks only if they enforce policy. Point
   them at the same allow-list.
3. Trim the skill into `reasoning.skill` (guide §4.3):
   - keep the method;
   - drop the fobo_* tool instructions, the rec/pattern input description and the old output
     format.
4. Set the environment variables: `PHOENIX_COLLECTOR_ENDPOINT` (or `AOF_TRACING_SETUP`),
   `AOF_ENTITLEMENT_URL`, `AOF_IDENTITY_HEADER`, `AOF_TRUSTED_PROXY_SECRET`.

Check:

```
scripts/aof_office_smoke.py --user <id> --case break.investigation --group <group> --key book=<book> --key cob=<cob>
```

It must pass, and the trace must show in Phoenix. Report the model, turns and cost per group.

## Phase 5 — Parallel run and parity

1. For each book and COB in the agreed period, export the FOBO run as CSV or JSON. Use one
   row per break, with id, category, side and verdict.
2. Run `scripts/fobo_aof_parity.py --old <file> --api <aof> --case-id <id> --user <id>`.
   Add `--old-columns` if the names differ.
3. Compare the deterministic breaks (`decided_by: playbook`) by diff; they must match
   exactly. Compare model-decided breaks by reading. Their wording may differ, but their
   verdict should not.
4. Log every difference in `PARITY_LOG.md`: book, COB, break, field, old, Agent One Finance, cause, and the
   decision (config fix, accepted per guide §6, or gap).
   - Fix config differences in the group file, through a new approved version.
   - Never change the engine.

Check: zero unexplained differences for the period on every book. Ask for Product Control's
sign-off.

## Phase 6 — Cut-over and retire (only after sign-off)

1. Set the Agent One Finance group's schedule live and turn off the FOBO trigger. Move users to Agent One Finance web.
2. Keep Agent One's FOBO deployment able to start for one month-end. Write down the rollback
   steps (guide §8) and test them once.
3. After a clean month-end, remove the retirement list in guide §3:
   - the orchestrator, rules code, fobo_* MCP tools and session reasoner;
   - FOBO's versioning and console.

   Make the FOBO tables read-only. Do not drop them.

Check: Agent One Finance is the only system that writes. Fill in the sign-off checklist in guide §10.

## What to report after each phase

- what you changed (files), and what you did not do and why;
- the check's command and its output (pass or fail counts);
- new gaps and open questions, numbered;
- the next phase, waiting for approval.
