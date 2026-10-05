# Runbook: evaluating a capability on the real model (office)

**Date:** 2026-10-05 · **For:** the Helix team and a capability's owners, in the office
environment where the model is reached through the Agent SDK.

In dev and CI the model is the deterministic **stub**: it proves the plumbing, never the
judgement. Before a capability or group goes live on the model, and after every change to its
instructions, sections, tools or model, run this.

## What it measures

An **eval** replays cases people already decided on the version under test, as hidden shadow
cases. Nothing is written back, and a shadow never reaches publish. Helix then compares each
group with the earlier decision:

| Score | Meaning | Target before go-live |
|---|---|---|
| **agree** | approved before, proposed now | the large majority of the model's groups |
| **disagree** | rejected before, proposed now | 0 on deterministic categories; investigate every one |
| **escalated** | sent to a person now | acceptable (safe), but it is lost automation |
| **verdict** | the same playbook verdict (FOBO) | equal on every deterministic group (the table decides them) |
| **wording** | 0–1 similarity to the approved explanation, judged by the model | trend only, not a gate |

Also look at:
- **sections**: required sections missing (`MISSING_SECTION`);
- **validation**: `UNGROUNDED_FIGURE` escalations;
- **cost**: each eval run, and each case, is a span in Phoenix with tokens and cost.

## 1. Prepare (once)

```bash
# apps/backend/.env in the office (never commit it)
HELIX_LLM_ADAPTER=agent_sdk
HELIX_LLM_MODEL=<the model your office approved>
HELIX_LLM_EFFORT=high
HELIX_LLM_MAX_TURNS=12
HELIX_LLM_MAX_BUDGET_USD=0.50          # per group: a runaway investigation stops here
# the Agent SDK's own credentials come from the office's approved secret store
PHOENIX_COLLECTOR_ENDPOINT=…            # see the tracing section of the developer guide
```

Then:
1. Run the office smoke test: `python scripts/helix_office_smoke.py`. It checks that the
   connectors, the gateway, one model call and tracing all work.
2. Set spend limits on the capability (`limits.max_cost_usd_per_case` and `…_per_day`). Over a
   limit, groups go to a person rather than failing.

## 2. Build the test set

An eval needs decided cases: approved and rejected groups, in the reviewers' own words.
- **New on Helix** (for example FOBO Prime): run Helix in *shadow* alongside today's process for
  one to two weeks. Controllers decide in Helix as they work, which gives at least 20 cases
  across the books.
- **Already live**: last month's cases are the test set.

Include the hard cases on purpose:
- judgement categories: K aged, M missing side, G corporate action, H novel, U adjustment did
  not clear;
- an answered question (the desk's answer must reach the model);
- a case with a tollgate note.

## 3. Run

In the console, go to *Capabilities → name → Evals → Run on a version*. Choose the draft (or the
live version after a model change) and the team group.

Or use the API:

```bash
curl -X POST "$HELIX/api/capabilities/break.investigation/evals" -H "$AUTH" -H 'Content-Type: application/json' \
  -d '{"team_group": "fobo-prime", "group_version": 3, "limit": 50}'
curl "$HELIX/api/evals/$RUN_ID" -H "$AUTH"         # scores, per case and per group
```

A run of 50 FOBO cases costs roughly the cases' groups that go to the model × the per-group
cost. Phoenix shows the actual cost.

## 4. Read the result

1. Investigate every **disagree**. Open the shadow case from the run. Either the instructions
   miss something, a tool returned less than the controller saw, or the earlier decision was
   wrong. Fix the instructions, tools or sections, not the scores.
2. Every **verdict** mismatch on a deterministic category is a playbook bug, not a model
   problem. The model does not decide those.
3. Look through **escalated** for reasons that repeat:
   - `MISSING_SECTION`: tighten the section hints;
   - `UNGROUNDED_FIGURE`: the model is computing figures, so tell it to cite;
   - `REASONER_ERROR`: turns or budget too low.
4. Check *Learning from the work*:
   - judgement calls approved unchanged are candidates for a rule;
   - unexplained items are candidates for a new check.

## 5. Decide

| Result | Action |
|---|---|
| no disagreements on deterministic groups, few on judgement, cost within the limit | a second owner approves the version; it goes live |
| disagreements on judgement groups only | keep `sme_review` (always on for judgement); go live with the reviewers watching for two weeks, then eval again |
| verdict mismatches or repeated ungrounded figures | do not approve; fix and run again |

Record the run id in the version note when approving. The eval stays on the capability's
history.

## 6. Re-run when

- the instructions, sections, tools, specialists or playbook change (every draft);
- the model or `HELIX_LLM_EFFORT` changes;
- a connector's data changes shape (check the *Data and parameters* panel first);
- monthly, on the last month's decisions, to catch drift.

The same runbook serves every capability. Only the test set and the targets above change: for
variance commentary, **wording** and **agree** matter most, and for cash the rules decide most
groups.
