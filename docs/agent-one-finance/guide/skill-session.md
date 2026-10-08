# Skill session: run a skill file as it is

**Date:** 2026-10-08

The simplest way to put a team's skill on Agent One Finance. An event (or a schedule, or a person)
opens a case; **one step**, `agent`, gives the model the skill, the case key and the tools the
capability allows, in **one session**. The model reads the data it needs itself, through the MCP
gateway, and returns one result per item it investigated (for FOBO, per break).

Use it on day one, before any rule is written, or for a team that wants its skill run unchanged.
Move work into rules later, one check at a time, where the business wants the same answer every
time (see *Compared with rules and the model* below).

## The whole configuration

`config/agent-one-finance/capabilities/break-investigation-skill.yaml` (FOBO):

```yaml
id: break.investigation.skill
case:
  key: [book, cob]
  scopes: { book: book }
  opens_on: event
  events: true
  opens_as: aof-scheduler
items:
  id_field: instrument          # what identifies a result
  amount_field: difference
steps: [agent]                  # the platform adds draft, validate, review, record
reasoning:
  reasoner: llm
  skill_file: skills/fobo-investigation-skill.md     # the skill, as a file
  tools: [mbrec.breaks, mbrec.break_history, motif.break_snapshots, motif.booking_events, motif.trades, cats.trades]
  verdicts: [ESCALATE, MONITOR, POST, CORRECT_AND_REPOST, DO_NOT_POST]
  escalate_verdicts: [ESCALATE]
  result_fields: [break_type, difference, category]
  sections:
    - { id: root_cause, label: Root cause, required: true }
review:
  roles: [FOBO_CONTROLLER]
```

MB Rec chooses the capability in its event:

```http
POST /api/events
X-AOF-Event-Secret: …
{"capability_id": "break.investigation.skill", "case_key": {"book": "PRIME-MB-04", "cob": "2026-09-24"}}
```

So one book can run as a skill session and another on the rules-and-model setup
(`break.investigation`), each chosen by the event.

## What happens in a run

1. **The event opens the case** for the book and COB, as the capability's service user.
2. **`agent`: one session.** The system prompt is the skill plus the platform's rules: use only these
   tools, cite only figures from them, give a verdict from the list, escalate when the evidence
   does not support a conclusion. The model calls the tools as the skill says (MB Rec's breaks,
   MOTIF snapshots, trades…). Every call goes through the gateway: allow-list, book scope, masking,
   an audit row.
3. **Results become items and decisions.** One result per break: verdict, comment, the skill's
   sections, the fields listed. One group per break by default; set `group_by` (e.g. `[verdict]`) to
   decide several at once.
4. **`validate`**: every figure in a result (comment, sections and its fields) must appear in a tool
   result the session read. One that does not goes to a person as `UNGROUNDED_FIGURE`. A verdict not
   in the list goes to a person as `NO_VALID_VERDICT`; an escalating verdict as escalated.
5. **`review`**: a controller decides every break. **`record`**: decisions are kept and teach the
   next run's priors. Nothing is written to a bank system.

## The skill file

`reasoning.skill_file` is a path under the config folder (`config/agent-one-finance/`); paths outside it
are refused. The file is read when the capability is loaded or synced, and its **text is stored in
the version**: every case keeps the exact skill it ran with, and a change to the file becomes a new
draft that a second owner approves (`python -m agent_one_finance.config_sync`). Editing the
instructions in the console replaces the file's text and drops `skill_file`.

A team group can do the same under `set.reasoning.skill_file`.

The skill should say which tools to call for what; the tool names and descriptions come from
`connectors.yaml`, and the model sees only the ones in `reasoning.tools`.

## Settings

| Setting | What it does |
|---|---|
| `steps: [agent]` | A whole workflow. The platform adds `draft`, `validate`, `review`, `record`; they cannot be dropped. `agent` cannot be mixed with `load`, `match`, `group` or `reason`. Data steps may run before it. |
| `reasoning.skill` or `reasoning.skill_file` | The skill. |
| `reasoning.tools` | The only tools the session can call (read tools). |
| `reasoning.verdicts` | The verdicts it may give each result. Empty: commentary only. |
| `reasoning.escalate_verdicts` | Verdicts that go to a person as escalated (e.g. ESCALATE). |
| `reasoning.result_fields` | Fields each result carries, shown as columns; their figures are validated too. |
| `reasoning.sections` | The answer in parts; a required one missing sends the result to a person. |
| `reasoning.specialists` | Subagents the session may hand work to. |
| `reasoning.max_turns` | The session's turn limit (default `AOF_LLM_SESSION_MAX_TURNS`, 40). |
| `limits` | Spend per case and per day; over the limit the case goes to a person without a model call. |

## Model adapters

| Adapter | In a session |
|---|---|
| `agent_sdk` (Claude Agent SDK) | One `query()` for the case, with the gateway-backed MCP tools and a structured result (`summary`, `results[]`). |
| `stub` | Reads every tool it can fill from the case key; one result per row of the first that returns items; the first verdict offered. For demos and tests. |
| An office adapter with only `reason()` | Still works: the whole case is one group, decided as one. Add `investigate(request, tools)` for per-item results. |
| `none` | The case goes to a person. |

## Compared with rules and the model

| | Skill session (`break.investigation.skill`) | Rules and the model (`break.investigation` + FOBO groups) |
|---|---|---|
| Set up | The skill file and a tool list | The skill turned into checks, tests, categories and a verdict table |
| Same data, same answer | No: the model's answer can vary | Yes, for everything the rules settle |
| Safety rules (an FO cause never posts, no invented thresholds) | In the skill's words only | In code, after the table and after the model |
| Model calls | Every case, the whole book | Only judgement groups |
| Figures checked, a person decides, audit | Yes | Yes |
| Large books | One session; very large books need a higher turn limit or `group_by` | No limit from the model |

A sensible path: start a team as a skill session, read what controllers decide for a few weeks
(*Learning from the work* lists the checks the decisions suggest), and move the mechanical parts into
rules once the business is ready.

Code: `steps.agent` (`agent_one_finance/steps.py`), `SessionRequest` and `run_session` (`llm.py`),
`investigate` (`llm_agent_sdk.py`). Tests: `tests/agent_one_finance/test_skill_session.py`.
