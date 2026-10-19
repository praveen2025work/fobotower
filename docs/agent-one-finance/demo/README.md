# Agent One Finance: executive demo (CIO and accounting MDs)

**Latest, for presenting live:** [`agent-one-finance-demo-silent.mp4`](agent-one-finance-demo-silent.mp4), 4 min 20 s,
no audio, recorded 2026-10-05 from the current app. You speak over it from
[`presenter-script.md`](presenter-script.md), which gives each scene's start time, what is on
screen and the words to say. Scenes 10–12 show the controllers' FOBO skill on MB Rec's breaks:
the tollgate, the skill's answer sections and sign-off checklist, and the next COB's
follow-through (an adjustment that did not clear stays open).

**Click-through copy of the app:** [`agent-one-finance-snapshot.html`](agent-one-finance-snapshot.html), one file
that opens in any browser with no setup. It is read-only and uses recorded dev data. Send it
to your team or open it after the video.

The snapshot, refreshed on 2026-10-19, covers three agents with their tasks and configuration:
Reconciliation investigation and Break investigation (the FOBO use case) and Month-end
accruals. Its 33 tasks were built that day:

- FOBO CATS vs MOTIF reconciliation for six Prime and four Rates master books, and the cash
  ledger: Friday's COB (16 October) signed off, two Prime books still waiting and overdue; COB
  19 October waiting for review;
- FOBO break investigation: COB 16 October signed off; COB 19 October with three books at
  the tollgate and three waiting for review (two Prime, one Rates), each with its proposals,
  playbook verdicts, judgement calls, run history and downloads; its eval set rerun over the
  signed-off tasks;
- month-end accruals for September, waiting for review.

Each task is named after its reconciliation and the master book's product, e.g. "CATS vs MOTIF:
USD swaps (RATES-LDN-01) · COB 2026-10-19", "MB Rec breaks: Govt bonds (PRIME-MB-01) · COB
2026-10-19", "Bank vs ledger: UK01 · 2026-10-19". The label is the team group's `case.label`;
the product comes from the reference data (`knowledge/fobo-reference.yaml`, each book's
`label`), which the subject template reads as `{book_label}`. The demo's books hold only their
product's instruments from 13 October.

The overview, inbox and notifications count only these agents. The platform pages
(operations, audit, authoring) are left out; Connectors is in. It is seen as Dana, who can
see every team, and nothing in it can be saved or approved.

The console calls capabilities **agents** and cases **tasks**. Configuration keys keep their
names (`case.key`, `$case.cob`), so the YAML is unchanged.

The console's motion is in the snapshot too:

- pages arrive with a short transition, cards and table rows come in one after another, and
  figures count up;
- loading shows shimmer bars, and a progress line runs under the frosted top bar;
- the current page glows in the sidebar, and work in progress has a live dot;
- switching theme opens the new theme as a circle from the switch;
- all motion stops when the viewer's system asks for reduced motion.

To rebuild the snapshot:

1. Copy the dev database and clear its cases, keeping capabilities, groups and their
   versions (the copy leaves your own dev data alone):

   ```bash
   psql postgresql://fobo:fobo@localhost:5433/postgres -c "create database fobo_demo template fobo"
   psql postgresql://fobo:fobo@localhost:5433/fobo_demo <<'SQL'
   begin;
   delete from aof_tool_call; delete from aof_document where case_id is not null;
   delete from aof_notification; delete from aof_retention_event; delete from aof_eval_run;
   delete from aof_case;   -- cascades to items, groups, decisions, gates, messages, requests
   delete from checkpoint_writes; delete from checkpoint_blobs; delete from checkpoints;
   delete from aof_scheduler_tick;
   -- past sign-offs the knowledge graph keeps as "seen before"; places, books and desks stay
   delete from aof_kg_edge where from_id like 'decision:%' or to_id like 'decision:%';
   delete from aof_kg_node where kind = 'decision';
   commit;
   SQL
   ```

2. Run the API on the copy (`AOF_DATABASE_URL=postgresql+asyncpg://fobo:fobo@localhost:5433/fobo_demo`)
   and `npm run dev`.
3. Build the tasks: `python build-demo-cases.py --today 2026-10-19 --no-sim
   recon.investigation break.investigation fin.accruals` (this folder; name no agents for all
   of them). It opens, runs and decides each task through the API as the right person, then
   reruns the evals. `--no-sim` leaves out the FOBO skill's curated books, whose COB is fixed
   at 9 October.
4. Record in `apps/web`. This snapshot (three agents with their tasks):

   ```bash
   SNAPSHOT_USER=dana SNAPSHOT_AGENTS=recon.investigation,break.investigation,fin.accruals \
   node scripts/capture-snapshot.mjs
   ```

   Add `SNAPSHOT_SCOPE=config` for the agents' configuration only (no tasks; steps 1 to 3 are
   then not needed), and leave out `SNAPSHOT_AGENTS` for every agent and the platform pages.
5. Run `npm run build:snapshot` in `apps/web`, and copy `dist-snapshot/agent-one-finance-snapshot.html` here.

The narrated version below (2026-10-04) is kept for sending to people who will watch it alone.

**Video:** [`agent-one-finance-demo.mp4`](agent-one-finance-demo.mp4), 3 min 06 s, 1280×720, with voice-over and
on-screen captions. It was recorded from the running app on 2026-10-04: the dev stack,
dev data, and the deterministic stub model (no live model calls).

## Running order

| Time | Scene | Message to land |
|---|---|---|
| 0:00 | Title | One governed platform: AI does the legwork, people make every decision |
| 0:12 | The problem | Breaks are investigated by hand: about 12 min each (FOBO's own basis), and every team builds its own tooling |
| 0:30 | Inbox | The work is done before the controller arrives (scheduled at 06:30, matched and classified) |
| 0:45 | FOBO Prime case | The business's own playbook decides: checks, tests, verdict table, owner. Unconfirmed thresholds are flagged, not assumed. |
| 1:11 | Guard and evidence | A front-office cause never posts (enforced in code). Every figure traces to a system call; anything untraceable goes to a person. |
| 1:27 | Ask about this case | Plain-English questions, answered from this case's data only, and audited |
| 1:37 | Sign-off | One decision per pattern; sign-off in seconds; evidence pack ready for audit |
| 1:49 | Rates group | Same engine and playbook, with the team's own books, thresholds and reviewers. A new team is configuration. |
| 2:02 | Authoring | New work (accruals, substantiation, intercompany) is drafted, checked, and goes live on a second owner's approval |
| 2:16 | Operations | Entitlements on every call, masking, audit, cost caps, one-click off switches |
| 2:34 | What it means | Investigating becomes reviewing; one decision per pattern; same controls everywhere; use cases as configuration |
| 2:52 | Next steps | Pilot on FOBO Prime and Rates, measure against the 12-minute basis, then accruals and substantiation |

## How to use it in the meeting

1. Play the video, or pause it at 1:37 and do the sign-off live from the user guide
   steps.
2. Then put up the time-saving arithmetic with **your own volumes**. The video's line
   "200 breaks a day × 12 min = 40 hours" is shown as *illustrative*. It is arithmetic on
   FOBO's 12-minute basis, not a measured result.
3. The platform's own **Overview → Hours saved (30 days)** tile shows the measured figure
   and its basis: items grouped into decisions × the declared manual minutes. In the pilot,
   that tile is the number to report.

## Likely questions

| Question | Answer |
|---|---|
| *Can the AI post something wrong?* | No. It only proposes. A reviewer approves every group, and a write-back needs a second person's release. Guards in code (e.g. R2) override the model, and the validate gate escalates any figure that does not trace to source data. |
| *Is our data safe with the model?* | Every data access goes through the gateway, which applies the caller's entitlements and data scope, and audits each call. Account numbers are masked and counterparties pseudonymized before the model sees anything. |
| *Which model and where does it run?* | In the office: the Claude Agent SDK, through the office agent platform. Traces go to Phoenix. The demo used a deterministic stand-in. |
| *What does it cost to run?* | Model spend is recorded per case, with caps per case and per day. Over a cap, the work goes to people. |
| *How is this different from the office agent platform?* | It builds on it. It uses the platform's MCP connectors, plugins and RAG, and adds the workflow, playbooks, four-eyes control, evidence and audit that accounting needs. |
| *How long to onboard a new process?* | If its systems are already connected: a configuration file, checked by the platform, approved by a second owner. A new system needs an MCP connector, onboarded once by the Agent One Finance team. |
| *What happens to FOBO?* | FOBO keeps running unchanged. Its rules run on Agent One Finance as configuration (Prime and Rates), so it can move across when the team chooses. |
| *How do we know it agrees with our people?* | Evals replay past decided cases on any new version, without writing anything, and report agreement before it goes live. |

## Re-making the video

The scene scripts used to make it are in this folder:

| File | Holds |
|---|---|
| `scenes.json` | Narration per scene |
| `record-scenes.mjs` | Playwright recording with captions and highlights |
| `mux-scenes.py` | Adds the voice-over and encodes each scene |

The voice-over used a local Piper text-to-speech voice (`en_GB-alan-medium`), so no
content left the machine. To use a human voice, record each scene's line over the same
timings and rerun the mux step.
