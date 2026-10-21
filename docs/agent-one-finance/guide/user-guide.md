# Agent One Finance user guide

**Date:** 2026-10-04 · For agent owners, preparers, reviewers and controllers.
Developers: see [`developer-guide.md`](developer-guide.md).

Every screenshot below comes from a real walk-through on the dev stack. A new agent,
**Accruals review**, is set up from nothing and run end to end. The FOBO CATS vs MOTIF Prime
and Rates groups then show the same screens for a reconciliation.

**Contents**

1. [The ideas in five lines](#1-the-ideas-in-five-lines)
2. [Who does what](#2-who-does-what)
3. [Find your way around](#3-find-your-way-around)
4. [Set up an agent](#4-set-up-an-agent)
5. [Run it: open a task](#5-run-it-open-a-task)
6. [Review and sign off](#6-review-and-sign-off)
7. [Team groups: FOBO Prime and Rates](#7-team-groups-fobo-prime-and-rates)
8. [Change an agent safely](#8-change-an-agent-safely)
9. [Operations, connectors and audit](#9-operations-connectors-and-audit)
10. [Everyday tasks](#10-everyday-tasks)

## 1. The ideas in five lines

| Term | Meaning | Example |
|---|---|---|
| **Agent** | A kind of work, written as configuration (a *manifest*) | Accruals review, Helix FOBO Agent |
| **Team group** | One team's settings for a shared agent | CATS vs MOTIF — Rates |
| **Task** | One unit of work: one entity and period, or one book and COB | `UK01 accruals · 2026-09` |
| **Item / group** | Items are the lines in a task; similar items are grouped, and **one decision covers a whole group** | the accrual lines of account 6200 |
| **Connector** | A bank system served over MCP; Agent One Finance reads from and writes to it only through the gateway | `gl.balances`, `motif.positions` |

A task always runs the same steps: get the items, explain them (by rules, the playbook or
the model), check every figure, and **wait for a person**. Nothing is written back to a
system until people have approved it.

## 2. Who does what

| Role | Does | In the dev stack |
|---|---|---|
| Agent owner | Writes and changes the configuration | carol, bob (finance) · erin (recon) |
| Second owner | Approves a change; the drafter can never approve their own (four-eyes) | bob approves carol's draft |
| Group owner | Changes only their team's group | frank, gina (Prime) · rita, raj (Rates) |
| Preparer / opener | Opens tasks (or the schedule opens them) | alice |
| Reviewer / controller | Approves or rejects each group, with a comment | bob · FOBO_CONTROLLER · FOBO_RATES_CONTROLLER |
| Releaser | Releases a write-back after review (four-eyes) | set per agent (`publish.approver_roles`) |
| Platform support | Off switches, connectors; **sees no task data** | pat |

You see only the tasks inside your data scope. For example, alice sees UK01 only, and
rita sees only her four RATES-LDN books.

> **Dev only:** pick who you are from the user menu at the top right. In the office,
> your identity comes from SSO and your roles from the entitlements service.

## 3. Find your way around

![Overview](img/01-overview.png)

| Menu | What it is for |
|---|---|
| **Overview** | Your numbers: open tasks, what is waiting on you, hours saved |
| **Inbox** | Every task waiting on *you*, across agents |
| **Agents** | The catalogue; open one to see its tasks, groups, configuration, flow, versions |
| **Operations** | Health, runs, costs, the live tail of connector calls, off switches, schedules |
| **Authoring** | Create an agent by answering questions (no model), from a BRD (a model drafts), a template or YAML; approve drafts |
| **Audit** | Every connector call, allowed or refused |
| **Connectors** | The onboarded systems and their tools |

The bell shows notifications for review needed, release needed, published, failed and
escalated. The moon icon switches between the Barclays light and dark themes.

![Inbox](img/02-inbox.png)

## 4. Set up an agent

You can start in any of these ways. Each one ends in a draft that **another owner approves**,
checked by the same platform validator.

| Start from | Needs a model? | When |
|---|---|---|
| **Answer questions** (the default tab) | No | You know the process; Agent One Finance asks what a task is, where items come from, whether to match two systems or investigate what another system found, what is material, how to group, who reviews, whether a model or a person settles what the rules cannot, a tollgate, who may be asked for evidence, a sign-off checklist and follow-through |
| **Describe it (BRD)** | Yes, to draft properly | You have a written requirement. With a model connected (the office Agent SDK), it drafts a full configuration. Without one, the tab says so and only picks the nearest template |
| **Template**: attestation, commentary, reconciliation, report validation | No | It is close to an existing pattern |
| **YAML**: paste a manifest, e.g. one from [`../examples/`](../examples/) | No | You already have it |

The tab you use is your choice. In a deployment with no model, *Answer questions* and
templates do everything, and the agent can still run without a model: choose *a person
(no model)* for what the rules cannot settle.

**Configurable steps.** In *Configure → Configurable steps*, add generic steps in the order
the work needs them. Each runs only when its condition holds, if you give one.

| Family | Steps |
|---|---|
| Data | reference data (FX rates, limits), computed fields, filters, currency conversion, bands, duplicates, roll-ups, your team's own tool |
| Accounting | recompute and compare (fees, interest), schedule over periods, is the period open?, journal entries, post journals (after a second person releases them) |
| Assurance | change over periods, unusual against history, consistency checks, sample, risk score, owner attestation |
| Orchestration | wait for an event, child tasks, draft a message, report |
| Acquisition | match several systems, file intake, read a document |
| Time and parties | clocks, timeline, related tasks, name screening (candidates only), send to the other party |

Steps that need a person first (attestation, sending a message, posting) are given their
tollgate when you add them. Who may approve how much is set under *Human review*:
- **Authority tiers**, in Agent One Finance or read from the bank's delegated-authority system: the roles
  that may approve, how many different people, and whether "Approve all" may include the group.
- **Decisions reserved for named people**: only they decide, never in bulk, and the model's
  proposal is withheld unless allowed.

Each step can run only when a condition holds. Items a step sets aside stay on the task with the
reason, and the task shows the data sets it used.

### Step 1: Draft (owner, e.g. carol)

1. Open *Authoring*.
2. Answer the questions and click **Build the agent**, describe the work and click
   *Draft agent*, or pick a template.

The draft appears on the right with its workflow, a check result ("Passes every platform
check", or a list of what to fix), and assumptions to confirm.

![Authoring from a template](img/10-authoring-template.png)

### Step 2: Edit and submit

Edit the YAML freely, add a note for the approver, and click **Submit for approval**. The
YAML is checked again on submit. The checks are:

- every tool is an onboarded connector tool;
- every expression is valid;
- the gates (validate, review, record) are present;
- the roles are set.

Here carol pasted [`accruals-review.yaml`](../examples/accruals-review.yaml):

![Submitted, waiting for another owner](img/11-authoring-submitted.png)

carol's own draft shows *needs another owner*. She cannot approve it.

### Step 3: Approve (a different owner, e.g. bob)

bob opens *Authoring → Drafts awaiting approval* and clicks **Approve**.

![Drafts awaiting approval](img/12-drafts-awaiting-approval.png)

The agent is now live in the catalogue as **v1**:

![Agents](img/13-agents.png)

### Step 4: Look before you run

Each agent page has these tabs:

| Tab | Shows |
|---|---|
| **Tasks** | Open a task; the list of tasks |
| **Flow** | The workflow drawn from the manifest: tools per step, gates (bold), pauses for people, schedule |
| **Configure** | The orchestrator step by step: which steps run, where the run stops for a person, and every step's settings (see [§7a](#7a-configure-the-orchestrator)) |
| **Evals** | Replay past decided tasks on a draft and score agreement before going live |
| **Versions** | Every version, who drafted and approved it, diffs, export for promotion |

![Flow](img/31-agent-flow.png)

![Configure](img/30-agent-configure.png)

![Versions](img/32-agent-versions.png)

## 5. Run it: open a task

A task opens in one of four ways:

| How | Configured by |
|---|---|
| **By hand**: *Agent → Tasks → Open a task* | always available to openers |
| **On a schedule**: e.g. 09:00 on the 3rd, or 06:30 on business days | `task.schedule` + `schedule_keys` (e.g. `{prev_month}`, `{prev_business_day}`) |
| **On an event**: another system says data has landed (`POST /api/events`) | `task.events: true` |
| **By API**: `POST /api/agents/{id}/tasks` | always |

To open one by hand, alice (a preparer for UK01) fills in the task key and clicks **Open
and run**:

![Open a task](img/21-open-task-form.png)

The run happens in the background. You can leave the page; the bell tells you when the task
needs review.

![After the run](img/22-task-after-run.png)

## 6. Review and sign off

The task workspace has three columns:

- **Left: proposals.** One per group, with its status (Proposed / Escalated), who proposed
  it (rule, playbook or model) and its verdict.
- **Middle: the selected proposal.** Its explanation, the lines behind it, and every
  connector call it used. The *Ask about this task* and *Run history* tabs are here too.
- **Right: the task.** Its key, manifest version, where the workflow is (a pause shows
  ⏸ **review**), evidence, legal hold, and call counts.

![Review](img/23-task-review-bob.png)

A reviewer (bob) can:

| Action | Notes |
|---|---|
| **Approve** a group | Optional explanation; it replaces the proposal's when given |
| **Reject** a group | A comment is required |
| **Approve all N proposed** | Bulk; escalated groups still need one-by-one decisions |
| **Investigate again** | Write what to check ("Check the October reversal"); the model looks again, up to `max_reinvestigations` |
| **Attach PDF or workbook** | Evidence is stored with the task and readable by the task's tools |
| **Evidence pack (PDF)** | One PDF for audit: configuration, findings, decisions, every data access, protection in force |
| **Legal hold** | Keeps the task beyond its retention period |

Some rules apply to every review:

- Large groups can need **two approvers** (`dual_review_when`, here at 250k or more).
- The person who opened the task may be barred from deciding (`opener_may_decide: false`).
- When every group is decided, the task is **recorded**.
- If the agent writes back (`publish`, or `post` for journals), a **second person
  releases** it, and only then is anything written. The write is idempotent.
- With **authority tiers**:
  - a group shows its tier ("over 250k: fin reviewer · 2 different people");
  - a group above your authority is refused to you;
  - "1 of 2 approvals (bob)" means someone else must also approve.
- A **reserved** group shows who decides it. Nobody else can, alone or in bulk.
- **Journals** proposed for a group show their lines, and whether they balance.
- **Messages** show as a draft, or as sent with who approved sending.
- A task **waiting** for an event shows what it waits for and until when.
  - If you may, you can mark the event as arrived.
  - A parent task shows its child tasks and how many have finished.
  - Clocks show *on time*, *due soon* or *breached*.

![Signed off](img/24-task-signed-off.png)

**Ask about this task** answers in plain words from the task's own data and read tools.
Every lookup is audited, and protected fields stay masked.

![Ask about this task](img/45-ask.png)

**Run history** shows each step, when it ran, and the state as it was at that moment.

![Run history](img/46-run-history.png)

## 6a. A task for a whole region: the Summary tab

FOBO's feed sends one event per FOBO group, region and COB once its CSV has loaded — Rates
EMEA, Rates APAC, Rates AMER, and the same for FI Credit. Each event opens one task (the
**CATS vs MOTIF — by FOBO group and region** group) that reconciles every book of that group in
that region: Rates EMEA is about 300 books and 2,800 positions a side. Each region is its own
task, with its own breaks, proposals, sign-off and Summary, worked by that region's controllers
(a controller sees only the groups and regions in their data scope).

Such a task opens on its **Summary** tab:

- **Totals**: the rows read from CATS and MOTIF and the books they cover; the breaks and the
  books they are in, and how many books reconciled clean; the gross and net amount; how many
  breaks are still to decide, in how many open proposals.
- **By desk → product → book**: what the group names in `task.summarize_by`. Open a desk to
  see its products, a product to see its books; each row shows its breaks, amounts, what is
  still open and the proposals its breaks are in. A proposal chip opens that proposal.
- **Proposals across the books**: each proposal covers every break with the same category and
  side across the region — e.g. *Settlement break · back office*, 128 breaks in 122 books —
  with its verdict, who proposed it (the playbook, a rule or the model) and the decision. One
  decision covers every break in it; the review rules apply as for any proposal.
- **Model session**: which proposals the playbook decided and which the model reasoned; the
  adapter and model; tokens, cost and turns where the adapter reports them, against the
  agent's cost limit; the lookups the model made (and any refused); the tools and specialists
  it was offered; and a skill session, if the agent ran one.

Tasks for one book (the Prime and per-book Rates groups) keep the Proposal tab as the place
they open on; their Summary shows the same parts for that one book.

## 7. Team groups: FOBO Prime and Rates

*Helix FOBO Agent* is one agent shared by several teams. Each group sets
only what the agent allows (`configurable`):

- sources;
- keys;
- tolerance;
- playbook;
- thresholds;
- instructions;
- reviewers;
- schedule.

![Recon groups](img/40-recon-groups.png)

The group page shows its people, what the group sets, and the configuration its tasks run
on:

![Prime group](img/41-prime-group.png)
![Rates group](img/43-rates-group.png)

A FOBO task puts the playbook's work in the proposal header: **category, side, verdict and
owner**.

- **Prime, PRIME-MB-04.** A JGB missing in MOTIF is C/BO → POST, *requires controller
  confirmation* because Prime's thresholds are not set yet. An EURUSD forward is E/FO →
  DO NOT POST (fix at the desk).

  ![Prime task](img/42-prime-task-mb04.png)

- **Rates, RATES-LDN-04.** ITRAXX MAIN is explained by test FO-6 finding A (pull factor
  event missing) → C/FO → DO NOT POST. CDX IG is D/BO → POST, *with no confirmation flag*,
  because Rates' thresholds are confirmed.

  ![Rates task](img/44-rates-task-ldn04.png)

The full Prime vs Rates comparison and more tasks are in [`../examples.md`](../examples.md).
The FOBO parity list is in [`../fobo-on-agent-one-finance.md`](../fobo-on-agent-one-finance.md).

The dark theme:

![Dark](img/60-dark-rates-task.png)

## 7a. Configure the orchestrator

The **Configure** tab of an agent, and the *Configure this group's orchestrator* section
of a group page, show the orchestrator one step at a time. Everyone can look; owners can
change it.

**On the left is the pipeline:**

| Mark | Meaning |
|---|---|
| Green dot | The step runs |
| Grey dot | The step is switched off |
| Lock | A gate: validate, review and record are always on |
| Hand | The run stops for a person before this step |
| Blue dot | You changed something in this step |
| Red number | Problems to fix in this step |

**On the right are the selected step's settings.** Choose from the lists rather than typing
YAML:

| Step | What you set |
|---|---|
| Start: what a task is | Its name, key, title, data scope, when it opens (manually, by API, on a schedule, by event) and its deadline |
| Thresholds | Named values. Leave one empty until it is confirmed: anything that depends on it is flagged for confirmation |
| Get the items | One system, or two systems matched: the tools, their arguments, the match keys and the tolerance |
| Enrich, Reference lookups | The extra reads joined onto the items, and the knowledge-graph lookups as of the business date |
| Playbook | Cause checks, categories, the verdict table (category × side), guards, validation tests, and which thresholds a verdict needs |
| Group | What items are grouped by, and how a group is named |
| Rules, then the model | Rules first; then the model or people; the model's tools (read only), instructions, specialists and spend caps |
| Human review | Reviewers, when an explanation is required, confirmation, what "Approve all" leaves out, two approvers, delegation |
| Record and follow-up | What decisions are learned across, tickets for owning teams, recurring items, Excel columns, retention |
| Write back | The write tool, one write per group or per task, and who releases it |
| Owners | Agent only: who may change it, and what each team group may set |

**Each edit is checked as you make it**, by the same checks a draft must pass. The bar at the
top says *Passes every platform check*, or how many problems there are. Each problem shows
on its step, in the server's words.

**When you are done,** choose *Review and submit*. You see every change as *before → after*.
Add a note and submit. This makes a draft. Another owner approves it under *Versions*, and
new tasks use it from then on.

**Tollgates.** On any step after the first, *Tollgate* makes the run wait there for a person.
Set who passes it and what they should check. For example, a tollgate before *Rules, then the
model* means a reviewer approves the matched data before the model is asked anything:

- the task appears in their inbox as **Tollgate**;
- the task page shows what has been done so far, with **Approve and continue** and **Stop
  the run** (stopping needs a reason; the task can be re-run as a new attempt);
- every decision is recorded on the task.

![Setting a tollgate](img/27-configure-tollgate.png)

![A task at its tollgate](img/26-task-tollgate.png)

**A team group sees the same steps** with the agent's settings locked. For example,
which steps run is the agent's choice. The group changes only what the agent's
*configurable* list allows, and the draft holds only those paths.

![A group's playbook](img/47-group-configure-playbook.png)

![A problem, shown on its step](img/48-group-configure-problem.png)

![Review and submit](img/49-group-configure-submit.png)

YAML is still there for those who prefer it: *Advanced: edit this group as YAML* on a group
page, and *Authoring* for a whole manifest.

## 8. Change an agent safely

1. **Draft** the change in one of these places:
   - the *Configure* tab, for the agent, step by step;
   - the group page, for one team's settings;
   - *Authoring*, for the whole manifest as YAML.
2. **Evals** (recommended). Shadow-run the draft on past decided tasks. It writes nothing
   and reports agreement, verdict match and wording similarity.
3. **Approve.** A different owner approves the draft and reads the **diff** in *Versions*.
4. New tasks run on the new version. **Past tasks keep the version they ran on.**

To move a version from UAT to production, use *Versions → export* (a checksummed bundle,
signed when a key is set). Then use *Authoring → Promote from another environment*. It
arrives as a draft and is approved there again.

## 9. Operations, connectors and audit

**Operations** shows:

- health (DB, LLM, tracing, entitlements);
- runs, cost and errors in the last 24 hours;
- the fleet of groups, and what is waiting on people;
- a live tail of connector calls;
- **off switches**: turn off an agent, group or connector, with a reason;
- **schedules**.

![Operations](img/50-operations.png)

**Connectors** lists the onboarded systems and their tools. Only these tools can be used,
by any agent.

![Connectors](img/51-connectors.png)

**Audit** lists every connector call: who, which tool, allowed or **refused**, rows, time.

![Audit](img/52-audit.png)

## 10. Everyday tasks

| I want to… | Do this |
|---|---|
| Work my queue | *Inbox* → open a task → decide each group |
| Re-run a task on new data | Task → *Re-run* (makes attempt 2; attempt 1 is kept) |
| Make the model look again at one group | Proposal → *Investigate again* with a note |
| Give auditors everything | Task → *Evidence pack (PDF)* |
| Stop an agent during an outage | *Operations → Off switches* → agent → reason → *Switch off* |
| Set a threshold Product Control just confirmed | Group page → edit `policy.<name>.value` → submit → the other owner approves |
| Add a new team to an existing agent | Add a group file (see the [developer guide](developer-guide.md#5-add-a-team-group)) |
| Add a new kind of work | *Authoring* → questions, BRD, template or YAML → submit → approve |
