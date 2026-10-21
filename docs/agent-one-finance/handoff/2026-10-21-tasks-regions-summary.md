# Handoff: tasks/agents rename, regional FOBO tasks, task Summary (21 Oct 2026)

**For Claude in the office repo.** These changes come from the `fobotower` repo on GitHub
(branch `main`, commits `0fd464f` to `3ce1c40`). The office code has diverged: it calls AWS
Bedrock through the Anthropic SDK. Port the behaviour below into the office code. **Keep the
office LLM adapter**; only make it report usage, as described in section 3.

## 1. Rename: case → task, capability → agent (clean break, no aliases)

| Old | New |
|---|---|
| tables `aof_case`, `aof_case_item`, `aof_case_dataset`, `aof_case_message`, `aof_capability_version` | `aof_task`, `aof_task_item`, `aof_task_dataset`, `aof_task_message`, `aof_agent_version` |
| columns `case_id`, `capability_id`, `case_key`, `root_case_id`, `parent_case_id` | `task_id`, `agent_id`, `task_key`, `root_task_id`, `parent_task_id` |
| API `/api/capabilities/...`, `/api/cases/...` | `/api/agents/...`, `/api/tasks/...` |
| config folder `capabilities/`; `case:`, `$case.cob`, `case.label` | `agents/`; `task:`, `$task.cob`, `task.label` |
| modules `cases.py`, `capabilities.py` | `tasks.py`, `agents.py` |
| web routes `/capabilities`, `/cases/:id` | `/agents`, `/tasks/:taskId` |

- **Migration:** `apps/backend/migrations/versions/b7d9f1a3c5e7_rename_case_to_task_capability_to_agent.py`.
  - Renames the tables, columns, constraints, indexes and sequences.
  - Rewrites the stored agent, group and task configurations, the platform's own JSON keys, and the notification and switch kinds.
  - Leaves alone what people and connectors wrote.
- **Events** now send `agent_id`. A payload with `capability_id` is rejected.
- **Unchanged:** ids such as `recon.investigation`, `team_group`, and role names.

## 2. One task per FOBO group, region and COB

FOBO's feed sends one event when its CSV has loaded. Each event opens one task covering every
book of that group in that region:

```json
{ "agent_id": "recon.investigation", "team_group": "cats-vs-motif",
  "task_key": { "group": 500081, "group_name": "Rates", "region": "EMEA", "cob": "2026-10-08" },
  "event": "FOBO CSV loaded" }
```

- **Group config:** `config/agent-one-finance/groups/recon.investigation/cats-vs-motif.yaml`.
  - `key: [group, region, cob]`
  - subject `"{group_name} {region} · COB {cob}"`
  - `scopes: { group: fobo_group, region: region }`
  - match on `[book, instrument]`
  - `resolve` sets `book_desk` and `book_product` from the reference data
  - `group_by: [category, side]`, so proposals span the region's books
  - `summarize_by: [book_desk, book_product, book]`
- **Task name:** `group_name` comes from the reference data (node `group:500081`). If the reference data doesn't have it, the event's `group_name` is used (`tasks.subject_facts`).
- **Connector tools the office must provide** (MCP, reading FOBO's CSV). Each row must carry `book`, `instrument` and `mtm`:
  - `cats.group_positions(group, region, cob)`
  - `motif.group_positions(group, region, cob)`
  - `motif.group_break_snapshots(group, region, cob)`
  - `motif.group_booking_events(group, region, cob, book?, instrument?)`

  See `config/agent-one-finance/connectors.office.example.yaml`.
- **Gateway:** a tool's `scope` may now be a list of rules that must all hold, for example
  `[{arg: group, key: fobo_group}, {arg: region, key: region}]`.
- **Entitlements:**
  - Controllers need the data scopes `fobo_group` (e.g. `"500081"`) and `region` (e.g. `EMEA`).
  - The service account in `opens_as` needs `"*"` for both.
- **Reference data:** the demo files are `knowledge/fobo-books-rates.yaml` and `knowledge/fobo-books-fi-credit.yaml`. Replace them with the real books (book → desk, product) and FOBO group names.
- **Task page:** a tool result is cut to its first 100 rows. The audit record keeps every row.
- **Removed:**
  - the per-book group `cats-motif-fi-credit`;
  - the agent-level Summary (`/api/agents/{id}/summary` and its endpoints);
  - `summarize_by` in the per-book groups.

## 3. Summary tab on each task (with the model session)

- **Endpoint:** `GET /api/tasks/{id}/summary` (`agent_one_finance/summary.py`) returns:
  - `sources`: rows and books read, and how many books were clean;
  - `items`;
  - `breakdown`: the items by `summarize_by`;
  - `proposals`: each one with its book count;
  - `model`: who proposed what, adapter and model, usage, cost limits, the model's lookups, and the tools and specialists it was offered.
- **Web:**
  - the tab is `components/task/TaskSummary.tsx`;
  - a task opens on its Summary when its group sets `task.summarize_by`;
  - `GET /api/tasks/{id}` now returns `summarize_by`.
- **Office action:** have the Bedrock adapter fill `ReasonResult.usage` with `input_tokens`, `output_tokens`, `cost_usd`, `turns`, `duration_ms` and `session_id`. Without these, the card shows "not reported by the adapter".

## 4. Tick proposals and decide them together

- **Web:** `components/task/SelectionBar.tsx`. Checkboxes appear in the Proposals list and in the Summary's proposals table. The bar takes one explanation, a confirmation tick and the checklist, then offers Approve N / Reject N.
- **API:** `POST /api/tasks/{id}/decisions/bulk` now also accepts `confirmed`.
- **Rules still applied to each proposal:**
  - escalated proposals need the explanation;
  - judgement calls (`review.bulk_exclude`) are left out of Approve but included in Reject.

## 5. Porting checklist

1. Diff or cherry-pick the commits above. Keep the office LLM adapter.
2. Run the migration on a copy of the office database first.
3. Change the feed to send `agent_id`. Add the four `group_*` connector tools.
4. Add the `fobo_group` and `region` data scopes to the entitlements and the service account.
5. Run `python -m agent_one_finance.config_sync` and have the owners approve the drafts.
6. Run the tests: backend `tests/agent_one_finance/test_fobo_regional.py`, web `src/pages/__tests__/TaskWorkspace.test.tsx`. If you use the office converter, run `npm run office:build` and `python3 office/build_history.py`.

## 6. Assumptions and open decisions

- The CSV holds positions by book and instrument for one group, region and COB. Sign-off is per proposal within each regional task.
- A big regional proposal (e.g. 128 settlement breaks in 122 books) is held back if any of its breaks fails a blocking test. To approve desk by desk instead, add `book_desk` to `group_by`.
