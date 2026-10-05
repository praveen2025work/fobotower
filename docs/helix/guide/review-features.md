# Review controls and everyday features

**Date:** 2026-10-04. Each feature here is switched on by configuration, in a capability's
manifest or in one team group's `set`. No feature is specific to FOBO; the FOBO Prime and
Rates groups simply use all of them.

| Feature | What people see | Configured by |
|---|---|---|
| [Business-word group names](#1-group-names) | "Redemption break · back office" instead of "category C, side BO" | `group_label`, `playbook.side_names` |
| [Bulk approval with exclusions](#2-approve-all-and-confirmation) | "Approve N straightforward". Flagged groups are left for one-by-one review | `review.bulk_exclude` |
| [Explicit confirmation](#2-approve-all-and-confirmation) | A tick box and the reviewer's own words before approving a verdict that needs confirmation | `review.confirm` |
| [Judgement marker](#2-approve-all-and-confirmation) | A "Needs your judgement" chip and a callout on calls the model investigated | always on (finding `sme_review`) |
| [Next action](#3-next-action-money-at-stake-and-the-inbox) | "Next: 3 groups to decide · 1 needs your confirmation · 1 judgement call" | always on |
| [Money at stake](#3-next-action-money-at-stake-and-the-inbox) | Total absolute difference per case, used to sort the inbox | `items.amount_field`, `items.amount_unit` |
| [Deadlines](#4-deadlines) | Due and overdue badges, plus reminders before the deadline and when it is missed | `case.due` |
| [Recurring items](#5-recurring-items) | A "3 runs" badge on an item, and a Recurring panel on the group page | `insights.recurring` |
| [Escalation tickets](#6-escalation-tickets) | A ticket raised for the owning team after review, shown on the group | `escalation` |
| [Excel download](#7-excel-download) | "Download Excel" on every case | `export.columns` (optional) |
| [Cover while away](#8-cover-while-away) | Hand reviews to a colleague until a date. Their decisions say "for frank" | `review.allow_delegation` |
| [Measured time saved](#9-measured-time-saved) | "Hours saved (measured)" on the overview, from time actually spent per group | always on |
| [Configure the orchestrator](#10-configure-the-orchestrator) | Owners change every step's settings without YAML, checked as they go | the capability's `configurable` list |

A group can set a feature only when its capability lists the path in `configurable`. The
reconciliation capability allows all of these paths.

## 1. Group names

```yaml
group_by: [category, side]
group_label: "{category_name} · {side_name}"     # any group-key field, plus these two with a playbook
playbook:
  side_names: { FO: front office, BO: back office, UNKNOWN: side not proven }
```

Without `group_label`, a group is named "field value, field value" as before.

## 2. "Approve all" and confirmation

```yaml
review:
  bulk_exclude: [confirmation, judgement]   # default; also: escalated, model
  confirm: tick_and_comment                 # or: tick, none
```

Every group carries flags, computed by `helix/review.py`:

| Flag | Meaning |
|---|---|
| `confirmation` | The playbook flagged the verdict "requires controller confirmation", because a policy threshold it depends on is unset (FOBO's P1) |
| `judgement` | A judgement call: the model investigated, and a subject-matter expert decides |
| `escalated` | Escalated by a rule, the playbook or the model |
| `model` | Proposed by the model |

How the flags are enforced:

- **Bulk approval.** The server refuses to bulk-approve a group whose flags appear in
  `bulk_exclude`, and says why. The screen leaves such groups out of the button.
- **Confirmation.** Approving a `confirmation` group needs `confirmed: true`, plus a
  comment when `confirm` is `tick_and_comment`. The decision records `confirmed`, and it
  appears in the evidence pack and the Excel download.

## 3. Next action, money at stake and the inbox

```yaml
items:
  amount_field: difference
  amount_unit: GBP
```

The draft step stores the case's `exposure`: the sum of the absolute amounts of the items
in scope.

The inbox has:

- **Filters:** overdue or due soon, needs confirmation, judgement calls, escalated,
  covering for others.
- **Sorting:** most urgent first (overdue, then due soonest, then oldest), most at stake,
  oldest, newest.
- **Badges:** each row shows the case's age and its deadline.

## 4. Deadlines

```yaml
case:
  due:
    from: cob            # "opened" (default) or a case-key date field (YYYY-MM-DD, or YYYY-MM = month end)
    business_days: 1     # Monday to Friday
    hours: 0
    at: "11:00"          # time of day, in HELIX_SCHEDULE_TZ
    warn_hours: 2
```

- `due_at` is fixed when the case opens.
- Every minute, the scheduler's leader runs `helix/deadlines.py`. It sends **due soon** to
  the reviewers, and **missed** to the reviewers and the owners.
- Each reminder is sent once per case, in the bell and to the Teams webhook.
- A case stops counting once it leaves review and release.

## 5. Recurring items

```yaml
insights:
  recurring: { same: [book], lookback_cases: 10, min_runs: 2 }
```

An item recurs when the same item id was in scope in an earlier run of the same group
whose `same` key fields match. For FOBO, that is the same book on earlier COBs. Re-runs of
one key count once.

The data is served in two places:

- `case.recurring` on the case: item id, run count and the earlier cases.
- `GET /api/capabilities/{id}/recurring?team_group=` for the whole capability or group,
  limited to cases the caller may see.

## 6. Escalation tickets

```yaml
escalation:
  tool: ticketing.create_ticket            # a write tool on a ticketing connector
  when: "action == 'approve' and (verdict == 'DO_NOT_POST' or status == 'escalated')"
  args:
    team: "{escalate_to}"
    title: "{subject}: {label}"
    description: "{comment}"
    priority: P3
```

The `record` step raises the tickets after people have decided:

- One ticket per matching group, idempotent per case and group.
- The call goes through the gateway as `escalate`.
- The gateway allows a write tool to `escalate` only when it is the manifest's own
  `escalation.tool` and someone has decided the group. The model can never call it.
- The result is stored in `helix_ticket`. A failed ticket is recorded and never fails the
  case.

**Expression fields.** `when` and the argument templates can use:

- the group's key fields, plus `label`, `total` and `count`;
- `verdict`, `status`, `category`, `category_name`, `side` and `escalate_to`;
- `action`, `decided_by` and `comment`;
- `case_id`, `subject`, the case key, and `policy`.

**Connectors.**

- In the office: `config/helix/connectors.office.example.yaml` has the `ticketing`
  (ServiceNow) entry.
- In dev: `helix.stub_connectors.finance:build_ticketing`.

## 7. Excel download

`GET /api/cases/{id}/export.xlsx` returns three sheets:

| Sheet | Rows |
|---|---|
| Items | Each item with its group, finding, verdict and decision, plus the item columns |
| Groups | Each group's finding, verdict, confirmation, decision, comment and ticket |
| Case | The case's key, status, version, due date and exporter |

The workbook is built from the same read as the case page, so it shows only what the
caller may see. To choose the item columns:

```yaml
export:
  columns: [instrument, desk, cats_amount, motif_amount, difference]   # default: items.display
```

## 8. Cover while away

```yaml
review:
  allow_delegation: true
```

To set it up, go to *Inbox → Cover while you are away*, choose a colleague and a date (at
most 60 days), and give a reason. The API is `POST /api/me/delegations`, and
`DELETE /api/me/delegations/{id}` ends cover early.

While the cover lasts:

- **What the colleague sees.** The absent reviewer's cases appear in the colleague's inbox,
  marked "for frank".
- **Where they may act.** Only on capabilities that allow delegation.
- **Whose rights apply.** The absent reviewer's own roles and data scope, as recorded when
  they handed over.
- **What is recorded.** Each decision records `decided_by` (the colleague) and
  `on_behalf_of` (the absent reviewer).
- **Safeguards.**
  - Maker-checker checks both people.
  - Dual review needs two different people counted both ways, so a colleague acting for
    you plus your own approval do not make two.

## 9. Measured time saved

- **What is recorded.** The console records how long the reviewer spent on each group
  before deciding (`review_seconds`). For bulk approval, the time on the page is shared
  equally across the groups.
- **How it is reported.** The overview sets this measured time against working each item
  by hand at the capability's declared `metrics.manual_minutes_per_item`. It shows the
  basis and the median seconds per decision.
- **The declared figure stays.** The declared "Hours saved" figure remains, with its own
  basis.

## 10. Configure the orchestrator

This replaces the earlier settings form, which covered only thresholds, reviewers, schedule
and deadline.

- **Where it appears.** The *Configure* tab of a capability, and the *Configure this group's
  orchestrator* section of a group page.
- **What it covers.** Every step of the workflow:
  - which steps run, and where the run stops for a person;
  - the item source and match;
  - enrich, reference lookups and the playbook (checks, categories, verdict table, guards,
    tests);
  - grouping, rules, and the model (tools, instructions, specialists, spend caps);
  - review controls, tickets, recurring items, export, retention and write-back.
- **Checked as you edit.** Each edit is checked by the server, with the checks a draft must
  pass. Problems show on their step.
- **What happens on submit.** You review the changes as *before → after*, then submit. For
  a group, only its configurable paths are sent. Another owner approves the draft. See the
  [user guide §7a](user-guide.md#7a-configure-the-orchestrator).

## 11. Investigation features (any capability)

Seven features, each switched on by configuration and used by FOBO, cash and variance
commentary in their own ways. The [features by capability](features-by-capability.md) matrix
shows each one's settings.

| Feature | What a person sees |
|---|---|
| **Answer in sections** (`reasoning.sections`) | the model's proposal as named parts, e.g. root cause, remediation, end state |
| **Sign-off checklist** (`review.checklist`) | yes / no / n/a questions above *Approve*, with Helix's answer next to each |
| **Follow-through** (`follow_through`) | on the earlier case: what cleared on the next run and what is still open; on the item: *carried · MONITOR* |
| **Learning from the work** (`insights.unexplained`, `.automation_after`) | on capability and group pages: what nothing explained, and what could be a rule |
| **Data and parameters** (derived) | on capability (Configure tab) and group pages: the fields each check reads, the thresholds still to confirm |
| **Chasing questions** (`requests.remind_after_hours`, `.escalate_after_hours`) | reminders to the people asked, then a notice to the reviewers |
| **Answers with a file** (`requests.allow_attachments`) | *Attach* when answering; the file is on the question and in the case's evidence |

Also: follow-up cases are marked *late items* in the inbox, and the day's case shows the day's
totals.

## Also in this release

- **Pages load on demand.** The first download dropped from 765 KB to 261 KB.
- **Platform details for platform support only.** The LLM and entitlement source, plus the
  model and refused-call tiles, show only to platform support.
- **Clear empty states for platform support,** which sees no case data.
- **"Data used"** replaces the second "Evidence" heading on the case page.
- **Table layout.** Numbers are right-aligned, long text wraps, and long group names wrap
  to two lines.

## Where it lives

| Area | Files |
|---|---|
| Backend | `helix/review.py`, `helix/escalation.py`, `helix/deadlines.py`, `helix/insights.py`, `helix/export.py`; `manifest.py` (`DueSpec`, `RecurringSpec`, `EscalationSpec`, `ExportSpec`, `review.*`, `group_label`, `side_names`, `amount_unit`) |
| Database | Migration `d224c0604a72`: `helix_ticket`, `helix_delegation`, case `due_at` / `due_notified` / `review_ready_at`, decision `confirmed` / `on_behalf_of` / `review_seconds` |
| Web | `components/Urgency.tsx`, `components/DelegationPanel.tsx`, `components/orchestrator/` (the configuration editor), `components/capability/RecurringPanel.tsx`, plus the case workspace, inbox and overview pages |
| Tests | `tests/helix/test_review_features.py`, `src/pages/__tests__/Features.test.tsx`, `src/components/orchestrator/__tests__/` |
