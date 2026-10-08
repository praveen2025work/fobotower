# How it runs, and evals

Two tabs on every capability page answer two questions:

- **How it runs**: what happens to a case, in order, and who acts at each point.
- **Evals**: before a change goes live, would it have decided the past the way people did?

## How it runs

The tab is drawn from the configuration, so it is never out of date. It reads top to bottom.

1. **A case opens**: when someone opens it, on a schedule, or when another system sends an event
   (MB Rec at end of day, for example).
2. **Phases, in the order the steps run.** Each phase says who acts:

   | Phase | Who | What happens |
   |---|---|---|
   | Get the data | System | Reads the items and the reference data beside them, through the approved connectors. |
   | Find the cause | Rules, no model | Checks and algorithms (equal and opposite, parts that add up, trend…) mark what they find; the playbook gives a category and a verdict. |
   | Propose a decision | Rules, then the model | Items are grouped for one decision each; rules settle what they can, the model investigates the rest with only the tools allowed. |
   | Check every figure | Platform, always on | Every figure in a proposal must come from the data read; otherwise it goes to a person. |
   | A person decides | People | Someone with the right role approves or rejects each group, in their own words. |
   | Record and act | System, after approval | Decisions are recorded for audit and learning; only approved outcomes are written back. |

3. **Each step** shows its plain name (the team's own label when there is one), the kind of step,
   one line on what it does, and the systems it reads (🔧). **Always on** marks a gate no
   configuration can remove.
4. **Tollgate** (the blue band) marks where the run stops until a person approves the work so far.
   For FOBO, that is before the model is asked.

The strip at the top is the same story at a glance: the phases in order and how many steps each has.

## Evals

### What an eval does

1. **Choose a version**: a draft before you approve it, or the live one after a model or
   instruction change. For a capability run by team groups (FOBO Prime, FOBO Rates), choose the group.
2. **Replay past cases.** Up to 20 of the most recent cases people already decided are run again
   in hidden copies. They use the same connectors (reads are audited as usual), write nothing, notify
   nobody, and appear in no one's inbox. A hidden copy runs through tollgates, since no one is there to
   pass them, and stops at review. Steps that need a person's own act (an attestation, a send, a
   write-back) keep their pause.
3. **Compare with people.** Each group the version proposes is matched with the same group people
   decided.

### How to run one

1. Open the capability, then **Evals**.
2. Pick **Version to try** (the live version by default) and, if asked, the **Team group**.
   The line under the controls says how many decided cases are ready to replay. If it says none,
   decide some cases first.
3. Press **Run eval**. The result appears under **Results** and updates by itself while it runs.
   It takes seconds with the stub model and a few minutes with a real one.

Owners of the capability, or of the team group, can run an eval. Anyone who can see the capability
can read the results. From the API:

```bash
curl -X POST localhost:8300/api/capabilities/break.investigation/evals \
  -H 'X-AOF-User: frank' -H 'Content-Type: application/json' \
  -d '{"team_group": "fobo-prime", "version": 5}'      # version omitted = the live one
```

### Reading the result

| Figure | Means |
|---|---|
| **Agree with people** | Share of past decisions this version would have proposed the same way: it proposed what people approved, escalated what they rejected, or escalated where people approved that same escalation verdict. |
| **Disagreed** | It proposed what people rejected. Open **Where it differed from people** to read both sides before approving. |
| **Escalated** | It sent to a person what people had approved. This is safe, but means less automation than before. |
| **Missing / new** | Groups that disappeared, or appeared: the grouping changed, so fewer decisions could be compared. A group with no proposal counts as missing, never as agreement. |
| **Same verdict** | Share with the same playbook verdict, when there is a playbook. |
| **Wording** | How close the new explanation is to the words people approved: the model judges this when one is connected, otherwise word overlap. |

**When to approve a draft:** agreement holds or rises against the live version's run, no
disagreement is left unexplained, and any rise in escalations is one you accept. The same scores are
in Phoenix (`eval.run`, with one `eval.case` per case).

**Example (dev stack, FOBO Prime, live version, 3 past cases):** 13 decisions compared, 85% agree,
2 escalated (the model's explanation was approved before; this version sends them to a person),
2 new groups, same verdict 100%.

For running evals on the real model before go-live, see [Real-model evals](real-model-evals.md).
