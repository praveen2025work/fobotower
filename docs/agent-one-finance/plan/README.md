# Delivery plan: Agent One Finance with the FOBO (Helix) use case

Core Agent One Finance, integrated with Agent One. It investigates FOBO breaks from MB Rec for Product
Control and posts approved adjustments to MOTIF through FAS.

Two-week sprints, Tuesday to Monday:

- Sprint 1 (22 Sep – 5 Oct): Diagnostics, about 70% built. Done.
- Sprint 2 (6 – 19 Oct): AOF skeleton on AWS (orchestrator service, database, console). Under way.
- Sprint 3 starts 20 Oct.
- Working version in UAT by 30 Nov (end of Sprint 5); go-live 14 Jan 2027 (Sprint 9).

| File | For |
|---|---|
| [`aof-fobo-plan.html`](aof-fobo-plan.html) | PMO and stakeholders. It shows the timeline, milestones, epics, ways of working, and stories by epic (filter by sprint). Open it in a browser. |
| [`AOF-FOBO-stories.csv`](AOF-FOBO-stories.csv) | The Jira import: 10 epics and 101 stories, as user stories with acceptance criteria. |
| [`AOF-FOBO-L1-plan.csv`](AOF-FOBO-L1-plan.csv) | Level 1: epics, milestones, sprints and the freeze, for Excel. |
| [`confluence/`](confluence/00-index.md) | Pages for the project space: overview, delivery plan, ways of working, requirements per epic, decision log, RAID log. |
| `plan_data.py`, `standards.py` | The single source for the plan. `standards.py` holds the story wording, releases, components, and the Definitions of Ready and Done. |
| `build_plan_html.py`, `build_confluence.py` | Run both in this folder after any change. They rebuild the page, both CSVs and the Confluence pages. |

## Importing into Jira (System → External system import → CSV)

1. Create the sprints (named **Sprint 1** to **Sprint 9**, as in the file), the releases (**R1 Working version**,
   **R2 Go-live**) and the components first. Sprint 1 is closed and Sprint 2 is active, so their stories come in as
   Done and In Progress; leave those rows out if the board already has them.
2. Map the columns:
   - **Jira Cloud:** `Issue ID` → Issue ID, `Parent` → Parent.
   - **Jira Data Center:** `Issue ID` → Issue ID, `Epic Name` → Epic Name, `Epic Link` → Epic Link.
   - Map `Labels` (three columns) to Labels, `Fix Version` to Fix Version/s, and `Component` to Component/s.
   - Map each `Blocked By` column to the issue link *is blocked by*.
   - Map `Team`, `Environment` and `Status` to your fields.
3. `Acceptance Criteria` is also inside the description. Map the column only if your Jira has that field.
4. Add any fields your project requires (for example an application ID) to the file before importing.

Users are already provisioned for interim skill testing, so the plan has no user-access stories.
