# Helix on the office agent platform — what to inherit, what is missing, what next

**Date:** 2026-10-04. Companion to [`aria-ai-reuse-map.md`](aria-ai-reuse-map.md).

## 1. Division of labour

The office agent platform already provides **MCP servers, plugins, and RAG / data-explorer
tools**, the **Claude Agent SDK** for model calls, and **Phoenix** for observability. Helix should
not rebuild any of these. Helix is the layer above them: it turns them into **governed finance
work**.

| The office platform gives | Helix adds on top |
|---|---|
| MCP servers (bank systems, RAG, data explorer) | An allow-list per capability, data-scope checks per call, an audit row and a trace per call, masking and pseudonyms between bank data and the model |
| Plugins (skills, subagents, hooks, MCP bundles) | Skills attached to a capability or a team group, versioned, with four-eyes approval |
| The Agent SDK (model loop) | Cases, items, proposal groups, rules before the model, figure grounding, human review gates, write-back only after a second person releases it |
| Phoenix (traces) | One trace per case run, plus `session.id` = case id, so a reviewer can jump from a case to its trace |

**How to inherit, not copy:**

- **An office MCP server** (including RAG and the data explorer) is onboarded as a Helix
  connector: one entry in `config/helix/connectors.yaml` with `transport: http` and its URL. It is
  then available to every capability, through the gateway. No code is needed.
- **An office plugin's skills** become a capability's or group's `reasoning.skill`.
- **An office plugin's MCP servers** are onboarded as connectors, as above. They are not loaded
  straight into the Agent SDK: a tool the model reaches outside the gateway escapes the
  allow-list, the scope check and the audit. The adapter keeps `strict_mcp_config` for this reason.
- **Agent SDK hooks** (PreToolUse / PostToolUse) are a second line of defence inside the model
  loop. They are worth wiring to the same policy as the gateway.

## 2. Are we still using LangGraph and the knowledge graph? Yes

**LangGraph runs every case:**

- each capability's `steps` list becomes a `StateGraph`;
- state is checkpointed in Postgres (`AsyncPostgresSaver`), so a run survives a restart and
  resumes where it stopped;
- `interrupt_before` gives the review and publish gates, so a case waits days for people without
  holding a process.

**The knowledge graph** (`helix_kg_node` / `helix_kg_edge`, bitemporal):

- the `record` step writes each approved decision as a node linked to the subject it explains;
- the next run's `group` step reads the most similar approved decisions as priors for the rules
  and the model.

It is deliberately thin today: decision → subject. The roadmap below widens it.

## 3. New since the last round: documents

The **documents** MCP service (`helix/mcp_services/documents.py`) is a real service, not a stub,
and is onboarded like any connector:

| Tool | Access | What it does |
|---|---|---|
| `list_documents` | read | PDF / Excel documents for an entity |
| `read_pdf` | read | Text page by page (pypdf) |
| `read_workbook` | read | Rows of a sheet keyed by its header row (openpyxl) |
| `render_pdf_report` | **write** | A PDF report with sections, tables and a sign-off block (reportlab). Publish step only, after release |

**Report validation** (`config/helix/capabilities/report-validation.yaml`) is the slide's
"Report Validation" use case, built from configuration only:

1. Match the management report (Excel) to `gl.balances` on account × cost centre.
2. A rule settles rounding.
3. The model explains the rest, using journal lines and the business's PDF commentary.
4. A preparer signs off.
5. A reviewer who did not sign off releases it.
6. One PDF validation report is written, with the evidence tables and the sign-off.
7. The case workspace offers it as a download, only to people who can see the case.

`publish.per: case` (new) makes one write per case instead of one per group. It comes with the
tokens `$approved`, `$sign_off`, `$case_id` and `$subject`.

**Next for documents:**

- Word in and out (python-docx);
- Excel out (an evidence workbook);
- upload into a case from the workspace;
- OCR for scanned PDFs;
- tables from PDFs (pdfplumber);
- swapping the folder for the office document store's API (same tools, same arguments).

## 4. What is still missing — worth adding

Each item below names where it comes from: **aria** = aria-ai has it (component reuse, see the
reuse map), **web** = a current technique, **new** = neither.

### Users — preparers, reviewers, controllers

| Feature | Why | From |
|---|---|---|
| **Ask about a case** (chat scoped to one case, answered through the gateway, cites tool calls) | "Why is 6300 different?" without reading every row | aria chat/* |
| **Bulk decide** with a required comment for escalated groups | 200 rounding breaks are one click; escalations still need words | new |
| **Scheduled and event-triggered cases** (COB, month-end, file arrived) | Cases open themselves; people only review | aria scheduling |
| **Case run history / replay** step by step from the checkpoints | "What did the model see on Tuesday?" | aria history/* + LangGraph time travel |
| **Attach evidence** (upload PDF/Excel into a case → documents service) | The business's support lives with the decision | new |
| **Notifications** (Teams / email: waiting on you, released, failed) | Nobody polls an inbox | new |
| **Ageing and SLA** on open groups | Controllers chase what is late | aria watchtower |

### Developers — capability owners, group owners, the Helix team

| Feature | Why | From |
|---|---|---|
| **Eval sets from approved decisions**, scored in Phoenix (LLM-as-judge plus the grounding check) | A skill or model change is measured before it goes live | aria evals + web |
| **Shadow runs**: a draft capability or group version re-runs last month's cases and diffs the outcomes | Safe change, evidence for the approver | new |
| **Skill editor with revisions**, **manifest diff** between versions | Owners review what changes, not YAML | aria plugin/* |
| **Workflow graph view** (steps, gates, tools, people) | One picture of a capability | aria workflow/* (React Flow) |
| **Capability templates** (recon, commentary, validation, attestation) | New use cases start from a working shape | aria AgentTemplates |
| **Promotion across environments** (dev → UAT → prod) with the same four-eyes | Change control the bank already expects | aria LifecycleManager |

### Run-the-bank — support, operations, control

| Feature | Why | From |
|---|---|---|
| **Cost and token budgets** per capability / group, with a cut-off | No surprise model spend | aria CostAnalytics |
| **Kill switch** per capability, group or connector | Stop one thing without a deploy | new |
| **Evidence pack export** (who approved what, refusals, masking in force) as a PDF via the documents service | Audit and SOX requests in minutes | aria SecurityCompliance + documents |
| **Connector SLOs and alerts** from the live probes and audit latencies | Know before users do | aria SystemStatus |
| **Retention and legal hold** on cases, tool results and documents | Records policy | new |

### Techniques to adopt (current, mid-2026)

- **Parallel reasoning across groups.** LangGraph runs eligible nodes in parallel per super-step,
  and `Send` fans out one task per proposal group. LangGraph 1.2's deferred nodes make "aggregate
  once all groups are done" a one-liner. This speeds up large cases.
- **Durable human-in-the-loop.** Already in use (`interrupt_before` plus Postgres checkpoints).
  Next is time-travel replay of a run for support.
- **The MCP 2026-07-28 specification.** The protocol is now stateless:
  - plain load balancing of connectors, which suits the bank's infrastructure;
  - elicitation through `InputRequiredResult`, so a connector can ask the reviewer a question
    mid-call;
  - hardened authorization;
  - formal extensions;
  - MCP Apps, UI templates rendered in a sandbox, so a connector can bring its own view into the
    case workspace.

  Helix's MCP SDK (2.3) already speaks this version.
- **Agent SDK subagents and hooks.** A subagent per specialist (FX, accruals, booking events)
  under one case. PreToolUse hooks enforce the gateway's policy inside the model loop too.
- **Knowledge graph plus vectors (GraphRAG).** Widen the graph to entities (account,
  counterparty, instrument, book) and evidence edges, then retrieve priors by graph neighbourhood
  plus pgvector similarity rather than by exact subject.
- **Structured outputs everywhere.** Already used for the model's verdicts. Extend them to
  authoring and to chat answers, so every answer can be validated.

## 5. Suggested order

1. **Users first:**
   - ask about a case;
   - bulk decide with required comments for escalations;
   - scheduled cases;
   - evidence upload into a case.
2. **Trust:**
   - eval sets and shadow runs in Phoenix;
   - the evidence pack PDF;
   - cost budgets and the kill switch.
3. **Scale:**
   - parallel group reasoning;
   - the knowledge graph widened plus vectors;
   - subagents per specialist.
4. **Developer experience:**
   - the skill editor and manifest diff;
   - the workflow graph;
   - templates;
   - promotion.

## Sources

- [The 2026-07-28 MCP Specification: A Stateless, Extensible Future](https://blog.mcpservers.org/posts/mcp-spec-2026-07-28)
- [MCP specification 2026-07-28 changelog](https://modelcontextprotocol.io/specification/2026-07-28/changelog)
- [What is LangGraph (2026)](https://futureagi.com/blog/what-is-langgraph-2026/)
- [LangGraph: stateful graphs and durable execution](https://learn.traeai.com/t/ai-engineering/phases/14-agent-engineering/13-langgraph-stateful-graphs.html)
- [Claude Agent SDK overview](https://www.morphllm.com/claude-agent-sdk)
- [Claude Code skills, subagents, hooks and plugins — a practical overview](https://medium.com/@mishra.shashank35/claude-code-skills-subagents-hooks-and-plugins-a-practical-overview-572de7cedb20)
