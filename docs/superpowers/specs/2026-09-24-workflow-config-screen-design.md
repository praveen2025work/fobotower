# Workflow Configuration Screen — Design

**Date:** 2026-09-24
**Status:** Approved in conversation, section by section
**Branch:** `feat/workflow-config-screen`

## 1. Purpose

The LangGraph investigation workflow is configured by
`config/workflow/fobo-investigation.yaml`. Changing it today means editing the
file, running the CLI validator and restarting the API, and nothing in the
console shows the configuration at all: the Graph run drawer lists the steps,
but the settings, pause points and reasoner are invisible.

This work gives Product Control a **Workflow** tab in the Helix console where
they can see the graph — every step tagged by who decides it (code, playbook,
reasoner, human) — and change it through a versioned, four-eyes process.

### 1.1 What the user decided

| Question | Decision |
|---|---|
| Who is it for, what does Save do | Versioned live config: PC users edit in the UI, the server validates, saves a new version with who/when, and only new runs use it |
| Scope of the first release | The graph editor only |
| Who can change the live workflow | Draft + second approver: a PC user drafts, a *different* PC user activates |
| Where versions live | The database is the authority. YAML is the import/export format. Git PR mirroring comes later |

### 1.2 Out of scope

- **Git PR mirroring** (option C): opening a PR for every approved version and
  turning merged hand edits into drafts. Deferred until a server-side GitHub
  token is approved.
- **Live run overlay** on the graph, and the **per-break decision path** in
  Helix. Not selected for this release.
- **Sign-off resuming the graph.** Known gap, recorded here: the decision
  endpoint writes decisions directly and never calls `resume_investigation`,
  so Helix runs stay parked before `review`. Not changed by this work.
- Editing the playbook, or adding new step types. The screen configures the
  steps the registry already has; it cannot invent one.
- Rate limiting. No endpoint in the API has it today; adding it is separate
  work.

### 1.3 What can actually be configured

The step list is mostly fixed by the registry (`app/workflow/registry.py`).
`rank` is the only removable step; `resolve`, `gather`, `group`, `reason`,
`draft`, `validate`, `review` and `record` are required, and the order is
constrained by each step's `needs`/`produces`. In practice a version changes:
`rank` on/off and its position, the pause points, the per-step settings, and
the reasoner.

## 2. Data model

### 2.1 `workflow_version` (new table, new Alembic migration)

| Column | Type | Notes |
|---|---|---|
| `number` | int, PK | 1, 2, 3… — the version's identity. Allocated as `max+1` inside the insert transaction. |
| `config` | JSONB | The full `WorkflowConfig`, dumped by alias (so the key is `validate`, as in YAML) |
| `status` | varchar(16) | `draft` \| `active` \| `superseded` \| `rejected` |
| `based_on` | int, nullable, FK → `number` | The active version this draft was edited from. Null only for the seed. |
| `note` | text | Required, 1–500 chars. Why the change was made. |
| `drafted_by` | varchar(64) | Caller `staff_id` |
| `drafted_at` | timestamptz | |
| `decided_by` | varchar(64), nullable | The second person |
| `decided_at` | timestamptz, nullable | |
| `reject_reason` | text, nullable | Required when `status = rejected` |
| `decision_key` | varchar(128), nullable, unique | The approve call's `Idempotency-Key` |

A partial unique index `uq_workflow_version_one_active ON (status) WHERE
status = 'active'` makes "exactly one active version" a database guarantee,
not a convention.

Nothing is ever deleted. Versions are immutable once written, except for the
status transition and the decision fields.

### 2.2 `investigation_session.workflow_version` (new nullable int column)

The version a run started with. Written by `ensure_investigation_session`,
which already runs before the graph starts. Null means the run predates this
feature and is read as version 1.

### 2.3 Seeding

The first read of the active version, when the table is empty, inserts the
current YAML as version 1, `status = active`, `drafted_by = decided_by =
"system"`, note `seeded from config/workflow/fobo-investigation.yaml`. The
seed runs under a Postgres advisory lock (the same pattern as
`ensure_fixtures`) so two concurrent first requests cannot both seed.

## 3. Runtime: how a run uses a version

### 3.1 The store — `app/workflow/versions.py`

A repository over `workflow_version`:

- `active(session) -> (number, WorkflowConfig)` — seeds if empty.
- `get(session, number) -> WorkflowVersion`
- `config_for(session, number) -> WorkflowConfig` — validated configs are
  cached in-process by number. Versions are immutable, so the cache never
  needs invalidating; only the *active number* is re-read, with one indexed
  query, whenever a new run starts or a request asks for it. An approval on one
  API instance is therefore visible to every instance without a restart.
- `list(session)`, `create_draft(...)`, `approve(...)`, `reject(...)` — the
  rules in §3.3.

### 3.2 Pinning

1. `run_investigation` reads the active version, writes its number into the
   initial state (`workflow_version`, added to `INITIAL_INPUTS`) and onto the
   `investigation_session` row, builds the graph from that version's config,
   and executes it inside `use_workflow(config)`.
2. `use_workflow` sets a `ContextVar`. `settings()` returns the bound
   workflow's settings when one is bound. The call sites in `gather`,
   `reason`, `validate`, `reasoning/registry.py` and the session service
   adapter do not change. LangGraph copies the context into the tasks it
   creates, so the binding reaches every step; a test proves it (§7.1).
3. When nothing is bound, `settings()` falls back to the YAML file, as today.
   Only the CLI and unit tests that call nodes directly hit this path. API
   request handlers that need settings outside a run (the Helix chat's
   "which reasoner" message) bind the active version explicitly.
4. Every reader of a run's checkpoint — `open_case`, `read_case`, the decision
   endpoint, the trace query — goes through one helper,
   `graph_for_session(checkpointer, session, session_id)`, which looks up the
   run's version from its `investigation_session` row and builds that
   version's graph. The trace's step list comes from the same version. A run
   started on v3 keeps showing v3's steps after v4 goes live.
5. `resume_investigation` also builds the run's own version, so when sign-off
   resume is eventually wired up, a paused run cannot pick up a newer config.

### 3.3 Rules

- Drafting and deciding both require the `PC` role (403 otherwise).
- A draft's config must pass `WorkflowConfig` validation — the same validator
  the YAML CLI uses (422 with every problem listed).
- A draft records `based_on` = the active number the editor started from.
- **Approve** requires: status `draft`; `decided_by != drafted_by` (403);
  `based_on` is still the active number (409 "vN went live after this was
  drafted"); an `Idempotency-Key` header that has not been used (409). On
  success, in one transaction, the draft becomes `active` and the previous
  active becomes `superseded`.
- **Reject** requires status `draft` and a non-empty reason (422). Anyone with
  PC may reject, including the drafter (withdrawing their own draft).
- A decided version cannot be decided again (409).

### 3.4 The `FOBO_REASONER` override

The environment variable still overrides the configured reasoner, for local
development. Because it can override an approved decision invisibly, `GET
/api/workflow` reports it under `overrides`, and the Workflow tab shows a
banner while it is in effect.

### 3.5 Dev caller switching

The auth stub has a single caller, so a second approver cannot exist. When
`FOBO_ENV=dev`:

- a middleware reads an `X-Dev-Caller` header into a `ContextVar`, and
  `current_caller()` returns that dev caller;
- the dev callers are `praveen` (roles FO, PC — the current stub) and `asha`
  (role PC);
- an unknown name is a 400 listing the valid names;
- `GET /api/workflow` returns `dev_callers` so the console can offer a switcher.

When `FOBO_ENV` is anything else or unset, the header is ignored and
`dev_callers` is omitted. The README's run command sets `FOBO_ENV=dev`.

## 4. API — `api/routes/workflow.py`, prefix `/api/workflow`

| Call | Returns |
|---|---|
| `GET /api/workflow` | `active` (number, config, note, drafted_by/at, decided_by/at), `steps` (catalogue, §4.1), `settings_schema` (field → type, min, max, default, description), `reasoners`, `overrides`, `pending_drafts` (count), `dev_callers` (dev only), `caller` |
| `GET /api/workflow/versions` | All versions, newest first: number, status, note, based_on, drafted_by/at, decided_by/at, reject_reason |
| `GET /api/workflow/versions/{n}` | The version's fields and config, plus `diff` against the active version (§4.2) |
| `GET /api/workflow/versions/{n}/yaml` | `text/yaml` download, same layout as the repo file, with a header comment naming the version, drafter and approver |
| `GET /api/workflow/versions/{n}/rebased` | For a stale draft: its changes re-applied on top of the current active version — `{config, based_on, conflicts}`. Not saved. (§4.3) |
| `POST /api/workflow/validate` | Body `{config}`. `{ok: true}` or `{ok: false, errors: [...]}`. Always 200: validation failure is the answer, not an error. |
| `POST /api/workflow/drafts` | Body `{config, note, based_on}`. 201 with the version. |
| `POST /api/workflow/drafts/yaml` | Body `{yaml, note}`, max 64 KB. Parsed with `yaml.safe_load`; a parse error is a 422 naming the line and column. `based_on` is the active version at the time of upload. 201 with the version. |
| `POST /api/workflow/versions/{n}/approve` | Header `Idempotency-Key` (required). 200 with the version. |
| `POST /api/workflow/versions/{n}/reject` | Body `{reason}`. 200 with the version. |

Errors use FastAPI's `detail`, like the rest of the API. Validation failures
return `detail: {"message": "workflow is invalid", "errors": [...]}` so the
console can list each problem; every other error's `detail` is a string.

### 4.1 Step catalogue

Each registry `Step` gains a `decided_by` field. The catalogue entry for each
step is `name, label, description, decided_by, removable, required_because,
can_escalate, needs, produces, must_follow`.

| Step | `decided_by` |
|---|---|
| resolve, gather, group, validate, record | `code` |
| reason | `playbook+reasoner` — the console shows the active reasoner next to the tag |
| rank | `code+model` — one cause is code; several need a model (not built) |
| draft | `template` — model planned |
| review | `human` |

### 4.2 Diff

A pure function, `diff(base: WorkflowConfig, other: WorkflowConfig) ->
list[Change]`, in `app/workflow/diff.py`. Each change is `{path, kind,
before, after}`:

- `steps`: `added`, `removed`, `moved` (with old and new index)
- `pause_before`: `added`, `removed`
- `settings.<step>.<key>`: `changed`

### 4.3 Rebase

A pure function, `rebase(base, draft, active) -> (config, conflicts)`, in the
same module. For each settings leaf, and for `steps` and `pause_before` as
whole lists: if the draft changed it relative to `base`, take the draft's
value; otherwise take `active`'s. If both the draft and `active` changed the
same item, take the draft's and report it in `conflicts`. The result is
validated before it is returned.

## 5. Console — the Workflow tab

A third header tab in Helix: **Pipeline · Agent Analytics · Workflow**. It uses
the existing tokens, light/dark themes, `Drawer`, and the double-confirm
`ConfirmDialog`.

### 5.1 Files

`apps/console/src/components/helix/workflow/`:

| File | Role |
|---|---|
| `WorkflowView.jsx` | Tab container: loads `/api/workflow`, owns view / edit / versions mode |
| `ActiveStrip.jsx` | Active version line, pending-drafts chip, override banner, action buttons |
| `WorkflowGraph.jsx` | The SVG/CSS graph, in view or edit mode |
| `StepCard.jsx` | One step: label, `decided_by` tag, lock, edit controls |
| `StepPanel.jsx` | Side panel: description, needs/produces, why locked, settings |
| `DraftEditor.jsx` | Edit state, debounced validation, note, save |
| `SettingsForm.jsx` | Settings grouped by step, bounds from `settings_schema` |
| `VersionList.jsx` | History with status chips |
| `VersionDetail.jsx` | Diff rendering, approve / reject / redraft |
| `YamlUpload.jsx` | File or paste, errors with line numbers |
| `DevCallerSwitch.jsx` | Header switcher, rendered only when `dev_callers` is present |
| `../data/workflowApi.js` | Every call the tab makes |

Each file stays under ~300 lines.

### 5.2 View mode

- **Active strip:** "v3 · drafted by praveen · approved by asha · 24 Sep
  14:10 · 'Lookback 180→90 days'", a "2 drafts awaiting approval" chip,
  the override banner, and **Download YAML**, **Upload YAML**, **New draft**.
- **Graph:** steps as cards, left to right, stacking vertically on narrow
  screens. Each card shows its label, a `decided_by` tag (code grey, playbook
  green, reasoner purple with the active reasoner's name, human blue, template
  grey) and a lock when it cannot be removed. A pause marker sits before each
  `pause_before` step. A dashed branch runs from each `can_escalate` step to
  "Escalate → end". Clicking a card opens `StepPanel`.

### 5.3 Edit mode

"New draft" copies the active config into the editor, `based_on` = active.

- Include/exclude toggle on removable steps.
- Up/down arrows to reorder. The UI does not encode ordering rules; the
  validator decides.
- Click the gap between two cards to add or remove a pause point.
- `SettingsForm` with bounds from the server, and a reasoner select.
- Every change triggers `POST /validate`, debounced by 400 ms. Errors are
  listed, and each one that names a step is also shown on that step's card.
  **Save draft** is disabled while there are errors or the note is empty.

### 5.4 Versions

- `VersionList`: every version with its status chip.
- `VersionDetail`: the diff as readable lines ("`gather.priors_lookback_days`
  180 → 90", "`rank` removed", "pause added before `reason`").
  - **Approve** (double-confirmed, sends a fresh `Idempotency-Key`) and
    **Reject** (reason required).
  - On the caller's own draft, Approve is disabled with "A second PC user
    must approve".
  - On a stale draft: "v5 went live after this was drafted" and **Redraft on
    v5**, which loads `/rebased` into the editor and lists any conflicts.

### 5.5 Elsewhere

- The **Graph run** drawer shows "Workflow vN" for the run.
- `apiClient` sends `X-Dev-Caller` when a dev caller is selected (kept in
  `localStorage`, read inside try/catch), and `post()` surfaces a structured
  `detail.errors` list instead of `[object Object]`.
- The `/classic` Execution tab's hardcoded file name becomes "Workflow vN".

## 6. Error handling

- Every 4xx carries a message the console shows as-is.
- A failed load of `/api/workflow` shows the tab's error state with a retry,
  like the board.
- A failed validate call (network) keeps the last result and shows
  "Couldn't check — retrying"; it never enables Save on its own.
- Approve/reject failures leave the dialog open with the server's message.

## 7. Testing

TDD throughout; new code at 80%+ coverage.

### 7.1 Backend (pytest, the existing Postgres test database)

- **Store:** the YAML seeds v1 exactly once, including under concurrent first
  reads; only one version is ever active (the index refuses a second);
  approve supersedes; reject requires a reason; nothing is deleted.
- **Four-eyes:** self-approve 403; non-PC 403; stale `based_on` 409; approve
  twice 409; reused idempotency key 409.
- **One validator:** the invalid configs in `test_workflow_config.py` are run
  through `POST /validate` and must produce the same messages.
- **YAML:** download → upload round-trips to an identical config; a parse
  error names its line.
- **Diff and rebase:** unit tests on the pure functions, including conflicts.
- **Pinning** (the key test): start a run on v1; approve v2, which removes
  `rank` and sets `priors_lookback_days` to 30. The v1 run's trace still lists
  `rank`, and its gather calls recorded a 180-day lookback. A new run uses 30
  days and has no `rank` step. This also proves the `ContextVar` binding
  reaches steps executed by LangGraph.
- **Live switch:** an approval is seen by a fresh store without a restart.
- **Overrides / dev caller:** `FOBO_REASONER` appears in `overrides`;
  `X-Dev-Caller` is ignored unless `FOBO_ENV=dev`; an unknown dev caller is a
  400.

### 7.2 Console (vitest + Testing Library)

- The graph renders from the catalogue: tags, locks, pause markers, escalate
  branch.
- The editor calls validate on change, shows errors on the right card, and
  keeps Save disabled while errors or the note are missing.
- Versions: Approve disabled on your own draft; stale drafts offer Redraft;
  upload errors render with line numbers; the diff renders each change kind.
- `apiClient` sends `X-Dev-Caller` when set and surfaces structured errors.

### 7.3 End to end (Playwright, new console dev dependency)

On a fresh test database, with `FOBO_ENV=dev`:

1. As `praveen`, draft "lookback 90 days".
2. Switch to `asha` and approve it.
3. Open a rec whose investigation has not run yet.
4. Its Graph run drawer shows v2, and the gather step's grounding calls show
   a 90-day lookback.
