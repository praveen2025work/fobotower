# Agent One Finance guides

Agent One Finance is the governed AI platform for Finance; FOBO is one of its use cases.

| Guide | For | What is in it |
|---|---|---|
| [User guide](user-guide.md) | Owners, preparers, reviewers, controllers | Screen-by-screen: set up a capability, configure its orchestrator step by step, approve it, open and run a case, review and sign off, team groups (FOBO Prime and Rates), change safely, operations. Includes screenshots. |
| [Developer guide](developer-guide.md) | Engineers | Architecture, running locally, the full manifest specification, steps and gates, expressions, playbooks, connectors and the gateway, knowledge graph, data protection, settings, HTTP API, extension points, testing, office deployment. |
| [Review controls and everyday features](review-features.md) | Both | Bulk approval exclusions, confirmation, deadlines, recurring items, escalation tickets, Excel download, cover while away, measured time saved, configuring the orchestrator: what each does and the configuration that switches it on. |
| [FOBO → Agent One Finance change guide](../migration/README.md) | Engineers moving FOBO in the office | Mapping from FOBO / Agent One to Agent One Finance, what to keep and retire, the model contract, invariants, phases, parity script, rollback, and a skill for office Claude Code. |
| [FOBO as an Agent One Finance capability — the walkthrough](fobo-capability-walkthrough.md) | Product Control, owners | Screen by screen: the capability and the FOBO Prime group, the skill's rules in the playbook, asking the desk, late exceptions. |
| [Configure it: FOBO on MB Rec's breaks](configure-fobo-mb-rec.md) | Owners | Step by step, with screenshots: breaks already reconciled upstream, timing differences, other sources, the desk's input at a tollgate. |
| [The FOBO skill in Agent One Finance](../fobo-skill/skill-to-agent-one-finance.md) | Product Control, owners | The controllers' FOBO Investigation Skill v1.0, section by section: what is codified in the playbook, what goes to the model, what a person decides; all its gaps are now built. |
| [UI principles](ui-principles.md) | Designers, engineers | Show the next decision, fold the rest: what is folded by default on each screen and how to build new screens the same way. |
| [Skill session](skill-session.md) | Owners, architects, engineers | Run a skill file as it is: one step, one model session with the MCP tools, the gates still on. The day-one option for any team, and how it compares with the rules-and-model setup. |
| [Algorithms](algorithms.md) | Owners, architects, engineers | The algorithm steps (equal and opposite, parts that add up, trend, same break in several places, near-identical references, Benford, robust anomaly, monetary-unit sampling, priority score), checks learned from decisions, and how FOBO uses them. |
| [Features by capability](features-by-capability.md) | Owners, architects | Every feature (sections, checklist, follow-through, insights, data contract, questions…) and how FOBO, cash, variance and report validation each configure it. |
| [FOBO Prime data contract and parameters](../fobo-skill/mbrec-data-contract.md) | MB Rec, MOTIF, Product Control | The fields each check and test reads, and the thresholds still to confirm, derived from the configuration. |
| [Questions by Teams or email](questions-by-teams-or-email.md) | Integration | The webhook payload, answering for someone with the event secret, files, chasing; a Power Automate recipe. |
| [Real-model evals (office)](real-model-evals.md) | Agent One Finance team, owners | Running evals on the Agent SDK before go-live and after every change; what to look for; go/no-go. |
| [Worked examples](../examples.md) | Both | FOBO CATS vs MOTIF Prime vs Rates with real runs; accruals, substantiation, intercompany, journal controls and suspense examples. |

The screenshots in `img/` come from the dev stack (stub model, dev users), dated 2026-10-04.
