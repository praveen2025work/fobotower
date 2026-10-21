# aria-ai → Agent One Finance: reuse map

**Date:** 2026-10-04 · Source: `praveen2025work/aria-ai` `platform-ui` (40 pages, 13 component
groups) and `enterprise-agent-platform` (eap-core). Companion to
[`aria-ai-assessment.md`](aria-ai-assessment.md).

The rule: **reuse aria-ai's components as they are** — copied with their own tests, fed by Agent One Finance
APIs that keep aria-ai's data shapes — and adapt only where a concept differs (an aria-ai *agent* or
*pack* is an Agent One Finance *agent* and its *team groups*; an aria-ai *run* is an Agent One Finance *task*).

Status: **Reused** = aria-ai code copied, unchanged or with a stated small adaptation ·
**Adapted** = same concept and visual language, rebuilt on Agent One Finance's model · **Planned** = next wave ·
**Replaced** = the office already provides it · **Not carried** = demo or product-marketing only.

## 1. For users — preparers, reviewers, controllers

| aria-ai | Agent One Finance | Status |
|---|---|---|
| Layout (sidebar, top bar, error boundary), StatCard, StatusBadge, DataTable, ErrorBoundary, design tokens | `apps/web` shell | **Reused** |
| Dashboard / MissionControl / Watchtower (home) | Overview: what waits on me, agents | **Adapted** |
| Approvals, `approvals/DecideModal` | Inbox (one queue across agents: review or release) + task sign-off | **Adapted**; DecideModal for the release confirmation — Planned |
| Run / RunConsole, `run/*` (RunWorkspace, RunPipelineStepper, RunTelemetryBar, RunOutputPanel…) | Task workspace — the 3-pane layout | **Adapted**; RunTelemetryBar (tokens, cost, turns) and RunPipelineStepper — Planned (wave 2) |
| Chat, `chat/*` (14 components: composer, message bubbles, tool trace, session context, slash commands…) | Ask about a task: chat scoped to one task, answered by the Agent SDK through the gateway | Planned (wave 2) |
| History, `history/*` (RunLaneDag, LaneToolReplay) | A task's run, step by step, from the LangGraph checkpoints | Planned (wave 2) |
| ScheduledRuns, `scheduling/PackSchedulesTab` | Scheduled tasks per team group (`task.opens_on: schedule`) | Planned (wave 2) |
| PacksHub, PackDetail | Agents catalogue; agent page with team groups | **Adapted** |
| `packs/PackFlow` | Agent flow diagram (steps, tools, people) | Planned (wave 3) |
| Documentation, Guides | In-app guide to the platform and each agent | Planned (wave 4) |

## 2. For developers — agent owners, team-group owners, the Agent One Finance team

| aria-ai | Agent One Finance | Status |
|---|---|---|
| PackAuthoring (BRD → pack) | Authoring (BRD → agent manifest, validated, second-owner approval) | **Adapted** |
| — (aria-ai had teams, not team configurations) | **Team groups**: each team configures an agent (FOBO rec groups such as CATS vs MOTIF) — owners, four-eyes, versions | **New in Agent One Finance** |
| Manifests (YAML view) | Group settings editor (YAML) | **Adapted**; agent manifest view + version diff — Planned (wave 3) |
| Plugins, `plugin/*` (SkillEditor, SkillSearchDialog, RevisionHistory, CommandsTab, HooksTab, ImportWizard) | Skill editor for an agent's / group's `reasoning.skill`, with revision history | Planned (wave 3) |
| Registry (live MCP fleet) | Connectors page (onboarded tools, read/write, data scope) | **Adapted** |
| AgentHub, AgentTemplates | Agent templates to start authoring from | Planned (wave 3) |
| WorkflowOrchestrator, WorkflowEditorPage, `workflow/*` (React Flow editor, run viewers) | Agent workflow graph (read-only first; steps and gates) | Planned (wave 3) |
| LLMSettings, ModelRouting | — | **Replaced**: the office's Agent SDK and model routing (`AOF_LLM_*`) |

## 3. For run-the-bank — support, operations, control

| aria-ai | Agent One Finance | Status |
|---|---|---|
| MissionControl, `mission-control/*` | **Operations** page | **Reused**: KpiTile, Sparkline, SeverityBadge, LiveTail, IncidentStrip, ScanningStrip, useStickyBottom (+ their tests) · **Adapted**: FleetTable (row = agent × team group), HealthBanner, McpServersPanel (Agent One Finance data) · ApprovalQueue → "Waiting on people" |
| SystemStatus | Operations health banner: database, LLM, tracing, entitlement; live connector probes | **Adapted** |
| Audit | Audit (connector calls, refusals, sign-offs, releases) | **Adapted** |
| ObservabilityHub | Phoenix (traces, sessions per task) + the trace link on every task | **Replaced** by Phoenix; a hub page of trace links — Planned (wave 4) |
| CostAnalytics, `watchtower/*` (CostChart, TimelineRibbon, AttentionCard, RecentRunCard) | Cost and volume per agent / group from model usage | Planned (wave 4) |
| Governance (policies) | Data-protection and write-tool policy (`governance.yaml`, `access: write`) — a read-only page | Planned (wave 4) |
| LifecycleManager | Agent and group versions (draft → active → superseded) | **Adapted** (versions + approval); promotion across environments — Planned |
| SecurityCompliance | Evidence pack: who approved what, refusals, masking in force | Planned (wave 4) |
| Permissions, Teams | — | **Replaced**: central entitlements (`AOF_ENTITLEMENT_URL`) |
| Settings | — | Planned only if a per-deployment setting needs a screen |

## 4. Not carried

Login (the office SSO proxy sets identity), Promote, MarketingHome, Solutions, Pricing — product
marketing for aria-ai as a product.

## 5. eap-core (backend) concepts

| aria-ai (eap-core) | Agent One Finance | Status |
|---|---|---|
| Governance: mask before prompt, audit, trace | `governance.py` — mask **and** reversible per-task pseudonyms | **Adapted** (extended) |
| Approval queue for gated actions | `access: write` tools + `publish` step released by a second person | **Adapted** |
| `brd_to_pack` authoring | `authoring.py` | **Adapted** |
| Precedent memory (pgvector) | Similarity priors behind `knowledge.similar_decisions` | Planned |
| Evals (framework, judges, PII corpus) | Eval sets from approved decisions, scored in Phoenix | Planned |
| Parallel specialist fan-out | Parallel reasoning across proposal groups (LangGraph `Send`) | Planned |
| Skills (SKILL.md packaging) | Skills per agent / group, edited in the skill editor | Planned (wave 3) |
| Scheduler | Scheduled tasks per group | Planned (wave 2) |
| SecretStore / Vault port | Connector credentials from the bank's vault | Planned |
| Langfuse tracing | — | **Replaced** by Phoenix (office standard) |
| Java DAG orchestrator, Node agent-runner | — | **Replaced** by LangGraph + Agent SDK |

## 6. Waves

| Wave | Scope | State |
|---|---|---|
| 1 | Shell and primitives; governance; authoring; team groups; Operations (Mission Control) | **Done** |
| 2 — users | Ask about a task (chat components); task run step by step (history components); scheduled tasks (scheduling); telemetry bar in the workspace | Next |
| 3 — developers | Skill editor with revisions (plugin components); workflow graph (React Flow); agent templates; manifest view and version diff | |
| 4 — run-the-bank | Cost and volume (watchtower components); governance and compliance pages; observability hub; docs and guides | |
