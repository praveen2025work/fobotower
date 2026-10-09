# Delivery plan: Agent One Finance with the FOBO (Helix) use case

Core Agent One Finance, integrated with the office Agent One, delivering FOBO break investigation
for Product Control. The working version is in UAT by 30 Nov 2026, and go-live is 14 Jan 2027,
across Dev, UAT and Prod.

| File | For |
|---|---|
| [`aof-fobo-plan.html`](aof-fobo-plan.html) | PMO and stakeholders: timeline, milestones, level 1 (epics), what the dates depend on, and level 2 (stories by epic, filterable by sprint). Open it in a browser. |
| [`AOF-FOBO-L1-plan.csv`](AOF-FOBO-L1-plan.csv) | Level 1: epics, milestones, sprint calendar, status and current state. Opens in Excel. |
| [`AOF-FOBO-stories.csv`](AOF-FOBO-stories.csv) | Level 2: 108 stories for Jira import. They are linked to their epics by `Issue ID` and `Parent ID`. |
| `plan_data.py`, `build_plan_html.py` | The single source of the plan. Edit `plan_data.py`, then run `python build_plan_html.py` in this folder. It writes both CSVs and the HTML. |

**Assumptions to confirm:**
- the team as listed on the page;
- Product Control availability for configuration (S1–S2) and UAT (S4–S5);
- a change freeze from 24 Dec to 3 Jan.

Users are already provisioned for interim skill testing, so the plan has no user-access stories.
