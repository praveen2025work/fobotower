# `apps/console` is the original FOBO console, not part of Agent One Finance

**For:** office Claude Code, comparing the upstream repository with the office repository.
**In short:**

- Leave `apps/console` out of every Agent One Finance (AOF) comparison, update and port.
- Do not copy any of its components into the AOF console.

## What `apps/console` is, and why it is in the repository

The repository has two applications, built at different times:

| | Original FOBO app | Agent One Finance |
|---|---|---|
| Started | 21 Sep 2026: the first use case, built before any platform existed | 3 Oct 2026: the platform; FOBO became one capability on it |
| Frontend | `apps/console` (Next.js, JSX, port 3100) | `apps/web` (Vite, React, TypeScript, port 5180) |
| Backend | `apps/backend/fobo` | `apps/backend/agent_one_finance` |
| FOBO is… | code: its own workflow, board and screens | configuration: the `break.investigation` capability, with its playbook and groups |

The original FOBO app stays in the repository for three reasons:

1. **It is the parity baseline.** The parity check (`apps/backend/scripts/fobo_aof_parity.py`) runs the same books and dates through the original FOBO app and through AOF, and compares the answers. That needs the original app.
2. **It shows the "before" picture for the FOBO migration.** It mirrors the FOBO the office runs today. The `fobo-to-aof` skill and the change guide (`docs/agent-one-finance/migration/README.md`) map each of its parts to AOF, as configuration.
3. **It still runs beside AOF** for demonstrations and comparison, as the main `README.md` says.

**It is retired once FOBO runs on AOF.** None of the AOF updates since 6 Oct have changed it; `whats-new.md` says the FOBO console "changed only in name".

## The rule

1. Exclude `apps/console/**` (and `apps/backend/fobo/**`) from the AOF comparison, update and test runs.
2. Do **not** port any `apps/console` component into the AOF console. The AOF console is `apps/web`, and it already has its own version of each.
3. Do not report `apps/console` files as missing from the office. They are not AOF files.
4. Leave the office's existing FOBO screens as they are until AOF goes live (14 Jan). They are retired after go-live, with the rest of the FOBO code.

## Where each `apps/console` part lives in AOF (`apps/web`)

| `apps/console/src/components/…` | AOF equivalent in `apps/web/src/…` |
|---|---|
| `mcp/Blocks`, `mcp/BreakDetailPanel`, `mcp/DataTable`, `mcp/ToolCall`, `lib/mcpColumns`, `lib/breakDetail` | The case page (`pages/CaseWorkspace.tsx`): the breaks table, the "Data used" fold with every system call, and `components/DataTable.tsx` |
| `workflow/DecisionTree`, `FlowGraph`, `FlowNodes`, `graphLayout`, `StepCard`, `StepPanel`, `WorkflowDialog`, `ErrorList`, `ActiveStrip`, `SettingsForm`, `workflowModel`, `yamlText` | Configure (`components/orchestrator/*`, checked live by the platform), How it runs (`components/capability/FlowDiagram.tsx`), and the group YAML editor (`pages/GroupDetail.tsx`) |
| `workflow/VersionTabs`, `VersionYaml`, `VersionList`, `VersionDetail` | The Versions tab: versions, diff, four-eyes approval |
| `session/AnalysisTurn`, `session/ReplyBlocks`, `lib/session` | The Model session tab (`components/case/SessionTranscript.tsx`) and "Ask about this case" |
| `board/BoardStatus`, `board/NotificationBell` | Overview, Inbox, `components/NotificationBell.tsx` |
| `ui/BookBar`, `ui/Kpi`, `ui/PipelineStep`, `ui/icons`, `lib/format`, `lib/uuid` | `components/StatCard.tsx`, `WorkflowStepper` and formatting in `components/ui.tsx`, lucide icons |
| `adjustments/RowDecision` (accept or reject per row) | Approve or reject **per group**, with the reviewer's words, the sign-off checklist and four-eyes approval. Approved adjustments are posted to MOTIF through FAS after a second person releases them. |
| `workflow/DevCallerSwitch`, `lib/apiClient` (dev-caller headers) | Not used in the office: identity comes from single sign-on. AOF's user switcher exists only on development stacks. |
| `src/aof/*` (an early view of AOF inside the FOBO console, route `/aof`) | Superseded by the AOF console (`apps/web`). Do not use it. |

## If the office console needs AOF screens

The recommended way is to deploy the AOF console (`apps/web`) as built, behind single sign-on.

Porting AOF screens into the office's Next.js console means re-translating them on every update. Porting `apps/console` screens is the wrong source: they belong to the original FOBO app, not AOF.

## What to report back

- the paths excluded;
- confirmation that no `apps/console` component was ported;
- any office screen that depends on `apps/console` code, so we can decide whether to keep it until go-live.
