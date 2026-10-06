# What changed since the office guide (2026-10-04 → 2026-10-06)

**For:** the office Claude Code running the [`upgrade-to-aof`](office-claude/upgrade-to-aof/SKILL.md)
skill, and the engineer signing it off. It lists everything upstream (`praveen2025work/fobotower`,
`main`) added after the FOBO change guide (commit `5c6392a`), what each change needs in the office,
and the files that carry it. All paths use the **new** names.

**The short version:**

- The platform is now **Agent One Finance**, with new names in the code, settings, headers, roles
  and tables ([`../renaming.md`](../renaming.md)). The converter
  `apps/backend/scripts/aof_convert.py` applies these names to any office copy.
- **Steps v2** adds 31 configurable step types and new engine features:
  - waiting states;
  - parent and child cases;
  - clocks;
  - an authority matrix;
  - decision boundaries.

  It also adds five example capabilities.
- The adapter contract for the office's LLM connector **gained fields but did not break**: an office
  `_run` keeps working. Two optional features need small additions in the office adapter (§4).
- **FOBO's answers did not change.** The FOBO playbook tests are unchanged and green. The new FOBO
  work is configuration: the MB Rec group, trade-level tools, and a Rates group.

## 1. Database migrations (run in this order by `alembic upgrade head`)

| Revision | After | What it adds |
|---|---|---|
| `e8f1a2b3c4d5` | `d224c0604a72` | tollgate decisions (a person approves the run's work before it goes on) |
| `f2a9c1d7e3b4` | `e8f1a2b3c4d5` | follow-up cases (late exceptions on an open book/COB) |
| `a3b5c7d9e1f2` | `f2a9c1d7e3b4` | information requests (questions to the desk, with reminders and attachments) |
| `b4c6d8e0f2a3` | `a3b5c7d9e1f2` | follow-through and the sign-off checklist |
| `c5d7e9f1a3b5` | `b4c6d8e0f2a3` | data sets on a case (steps v2 phase 1) |
| `d6e8f0a2b4c6` | `c5d7e9f1a3b5` | waiting states, parent/child cases, clocks (steps v2 phases 2–6) |
| `e7f9a1b3c5d7` | `d6e8f0a2b4c6` | **the rename**: `helix_*` → `aof_*` tables, indexes, constraints and sequences; role names and the scheduler user in stored data; checkpoint thread ids `helix:` → `aof:` |

The office head must reach `d224c0604a72` first. If the office added its own migrations, put
them after `e7f9a1b3c5d7` (set their `down_revision`), and rename any `helix_` table names in
them by hand. Every migration has a working `downgrade`.

## 2. Features, and the files that carry them

| Feature | Backend (`apps/backend/agent_one_finance/`) | Web (`apps/web/src/`) | Config / docs | Tests (`apps/backend/tests/agent_one_finance/`) |
|---|---|---|---|---|
| Tollgates: a person approves the work so far | `workflow.py`, `runner.py`, `review.py` | `pages/CaseWorkspace.tsx` | developer guide §7a | `test_tollgates.py` |
| Orchestrator editor (configure steps in the console) | `workflow.py`, `capabilities.py` | `components/orchestrator/*` | developer guide §7 | `web: OrchestratorEditor.test.tsx` |
| FOBO on MB Rec's breaks (no re-matching) | config only | — | `capabilities/break-investigation.yaml`, `groups/break.investigation/fobo-prime.yaml`, `fobo-rates.yaml`, `guide/configure-fobo-mb-rec.md`, `fobo-skill/*` | `test_break_investigation.py` |
| Ask for evidence: questions, reminders, attachments, bot payload | `asks.py`, `notify.py` | `components/QuestionsForYou.tsx`, `case/RequestsPanel.tsx` | `guide/questions-by-teams-or-email.md` | `test_asks.py` |
| Late exceptions open a follow-up case | `cases.py`, `scheduler.py` | `pages/Inbox.tsx` | — | `test_lifecycle.py` |
| Follow-through: re-check decisions in the next run | `follow_through.py` | `case/FollowThroughPanel.tsx` | — | `test_follow_through.py` |
| Answers in sections, sign-off checklist | `checklist.py`, `llm.py` (`sections`) | `case/SignOffChecklist.tsx` | — | `test_sections_checklist.py` |
| Learning: what nothing explained, rule candidates | `insights.py` | `capability/LearningPanel.tsx` | — | `test_learning.py` |
| Data needed and parameters to confirm | `contract.py` | `capability/DataContractPanel.tsx` | `fobo-skill/mbrec-data-contract.md` | `test_contract.py` |
| Guided authoring (answer questions, no model) | `authoring.py` | `components/authoring/GuidedForm.tsx`, `pages/Authoring.tsx` | `templates/*` | `test_guided_authoring.py` |
| **Steps v2 phase 1**: data sets, derive, filter, convert, bucket, aggregate, dedupe, transform, `when` on any step | `stepkit.py`, `workflow.py` | `orchestrator/PrepareSteps.tsx`, `case/DataSetsPanel.tsx` | `design/step-catalogue-v2.md`, developer guide §7b | `test_data_steps.py`, `test_steps_v2.py` |
| **Steps v2 phases 2–6**: journals and posting, assurance (flux, sample, attest), orchestration (await, spawn, report), acquisition (intake, extract), time and parties (clock, timeline, screen, outreach) | `steps_v2.py`, `authority.py`, `timekeeping.py`, `runner.py`, `views.py` | `case/StepsV2.tsx`, `pages/CaseWorkspace.tsx` | developer guide §7b, "The other families", "Authority and decision boundaries" | `test_step_types_v2.py` |
| Example capabilities | stubs: `stub_connectors/banking.py`, `stub_connectors/finance.py` | — | `capabilities/fin-accruals.yaml`, `client-complaints.yaml`, `controls-operating-test.yaml`, `controls-sample-test.yaml`, `payments-exceptions.yaml`; office entries in `connectors.office.example.yaml` | `test_step_types_v2.py`, `test_examples.py` |
| Platform overview and pitch page | — | `public/pitch/index.html` (served at `/pitch/`), `scripts/inline-pitch.mjs` | `platform-overview.md`, `pitch/agent-one-finance-pitch.html` | — |
| Console graphics (modern CSS) | — | `index.css` (`hx-*` classes), `pages/Overview.tsx`, `components/Layout.tsx` | — | web tests |
| The rename | every file | every file | `renaming.md`, `migration/rename-map.json` | all |

The FOBO console (`apps/console`) changed only in name (`src/aof/`, the route `/aof`). The
`fobo` backend package gained trade-level tools and the missing-side check (`fobo/`). Take
those only if the office still runs this repo's FOBO; the office's own FOBO on Agent One
is moved by the `fobo-to-aof` skill instead.

## 3. Settings and outside systems

| Change | Office action |
|---|---|
| Every `HELIX_*` setting is now `AOF_*` (same suffix) | rename in the environment, the secret store, Helm/compose files and CI |
| Headers `X-AOF-User`, `X-AOF-Event-Secret`, `X-AOF-Proxy-Secret`, `X-AOF-Webhook-Secret` | change the reverse proxy, the bots and any webhook senders (`AOF_IDENTITY_HEADER` and `AOF_PROXY_SECRET_HEADER` can keep the old user and proxy header names during the cut-over; the event and webhook header names are fixed) |
| Roles `AOF_*_OWNER`, `AOF_PLATFORM_ADMIN`; entitlement lookup `?app=aof` | add them in the entitlement system before the deploy, beside the old ones; remove the old ones after |
| Trace attributes `aof.*` (was `helix.*`) | update Phoenix saved queries and alerts |
| MCP server name `aof` (`mcp__aof__…`) | update any Agent SDK hook or allow-list that names `mcp__helix__` |
| Browser storage `aof.user`, `aof.theme` | nothing; users choose their user and theme once more |

To list the settings the code reads, run `grep -rhoE 'AOF_[A-Z_]+' apps/backend/agent_one_finance | sort -u`.
Compare it with the office's deployment files.

## 4. The office's LLM adapter

The contract in `agent_one_finance/llm.py` is the same shape: `name` and
`async reason(request, tools) -> ReasonResult`. New fields all have defaults:

| New | Where | What the office adapter should do |
|---|---|---|
| `ReasonRequest.notes` | tollgate notes and context lines | pass them to the model (the reference adapter adds them as `notes_from_people`) |
| `ReasonRequest.sections` and `ReasonResult.sections` | answers in sections | ask for one field per section and return `{section id: text}`; without it, sections show "not established" |
| `ExtractRequest` and `async extract(request) -> dict` | the `extract` step | optional; without it, `extract` reads only fields with a `pattern`, and the rest go to a person |
| Trace attributes `aof.llm.*` | reference adapter | keep the prefix if the office copied the span code |

If the office kept the reference adapter and replaced only `_run`, take the new
`llm_agent_sdk.py` and paste the office `_run` back in. That is all.

## 5. Proved here

The converter was run on the commit before the rename (`b389cf3`) and compared with the real
rename (`7165897`). It matched except for:

- the files that commit added: the migration and `renaming.md`;
- old design notes;
- one FOBO chat string, which it lists for a person to decide.

On the converted copy:

- backend: 740 passed;
- web: 92 passed;
- FOBO console: 192 passed;
- `tsc`: clean.
