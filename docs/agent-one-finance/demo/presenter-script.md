# Agent One Finance demo: presenter script (silent video)

**Video:** [`aof-demo-silent.mp4`](aof-demo-silent.mp4), 4 min 20 s, 1280×720, no
audio. Recorded on 2026-10-05 from the current app: light theme, the dev stack, dev data and
the deterministic stub model (no live model calls).

**How to use it.**
- Play the video and read each line when its scene starts.
- The lines are written at about 150 words a minute, so you can say them at a normal pace
  and finish with a moment to spare.
- A small **"3 / 17"** in the bottom-left corner of the video shows which scene is playing. If
  you fall behind, skip to that scene's line.
- The short caption on screen sums up each scene, so the video still makes sense if the room
  can't hear you.

| # | Starts | Length |
|---|---|---|
| 1 | 0:00 | 12 s |
| 2 | 0:11 | 14 s |
| 3 | 0:25 | 14 s |
| 4 | 0:39 | 20 s |
| 5 | 0:58 | 27 s |
| 6 | 1:25 | 9 s |
| 7 | 1:34 | 20 s |
| 8 | 1:54 | 12 s |
| 9 | 2:06 | 20 s |
| 10 | 2:26 | 17 s |
| 11 | 2:43 | 15 s |
| 12 | 2:57 | 15 s |
| 13 | 3:12 | 14 s |
| 14 | 3:26 | 14 s |
| 15 | 3:39 | 17 s |
| 16 | 3:56 | 13 s |
| 17 | 4:08 | 11 s |

---

### 1 · 0:00 — Agent One Finance *(title card)*

> This is Agent One Finance: one governed platform where our accounting teams run reconciliations, reviews
> and commentary. The AI does the legwork. Our people make every decision.

### 2 · 0:11 — The problem today *(card)*

> Today every break is investigated by hand: pull the data, find the cause, write it up, chase
> the sign-off. About twelve minutes a break, and every team builds its own tools.

### 3 · 0:25 — Overview *(Frank, FOBO controller)*

On screen, each in turn: hours saved; awaiting review and overdue; escalated; his inbox.

> This is what Frank, a FOBO controller, sees when he logs in: hours saved, what is waiting
> for his review, what is overdue, and what has been escalated to a person.

### 4 · 0:39 — Inbox

On screen: the most urgent case, the "at stake" amount, then the **Needs confirmation**
filter.

> The work is done before he arrives. At six thirty, Agent One Finance opened yesterday's run for every
> Prime book, matched CATS to MOTIF and classified every break. The inbox puts the most urgent
> first, shows what is at stake, and filters to what needs his confirmation.

### 5 · 0:58 — A case *(PRIME-MB-04, COB 24 Sept)*

On screen:
1. the "Your review" card;
2. the redemption break (back office, POST) and its "requires controller confirmation"
   warning;
3. "Approved before".

> In a case, the card at the top says exactly what is needed: three groups to decide, one
> needs confirmation, one is a judgement call. This redemption break is back office, so FOBO's
> playbook says post. But the materiality threshold is not confirmed yet, so Agent One Finance asks for
> his confirmation instead of assuming. He can also see how this break was approved before.

### 6 · 1:25 — Rule R2

On screen: the front-office group (side: front office, verdict: DO NOT POST).

> A front office cause never posts. That rule is enforced in code, whatever the table or the
> model says.

### 7 · 1:34 — Escalated *(PRIME-MB-04, COB 22 Sept)*

On screen: the novel break, "needs your judgement", then the card "Escalated — a person
decides" with "What you can do".

> When Agent One Finance cannot prove something, it escalates. This novel break has no proven side, so a
> person decides. The card says why in plain words, who owns it, and what the reviewer can do:
> approve with their own explanation, reject, or send it back to investigate again.

### 8 · 1:54 — Ask about this case *(Rita, Rates controller)*

On screen: a question is typed and answered; the answer's byline (which model answered, and
its audited lookups) is highlighted.

> Controllers can ask questions in plain English. Answers come only from this case's data, and
> every lookup is audited.

### 9 · 2:06 — Sign-off

On screen:
1. the proposals list;
2. **Approve 2 straightforward**;
3. the case turns to **Done** ("2 groups signed off by rita; 2 tickets raised for the owning
   teams");
4. the ticket numbers;
5. **Download Excel**.

> Breaks are grouped into patterns, so one decision covers many breaks. One click approves the
> routine groups; anything needing confirmation or judgement stays for one-by-one review. Once
> signed off, tickets go to the owning teams, and the evidence pack and Excel are ready for
> audit.

### 10 · 2:26 — The controllers' skill *(Frank, FOBO Prime on MB Rec's breaks)*

On screen: a break run stopped at **Your tollgate** (the check, "the model has not been asked anything yet"), the breaks and their categories, then Frank types the desk's note and **Approve and continue** is highlighted.

> Prime now starts from the breaks MB Rec already reconciled. The controllers' skill
> classifies each one, and the run stops at a tollgate: Frank checks it and adds what the desk
> said, before the model is asked anything.

### 11 · 2:43 — The skill's answer and sign-off

On screen: an aged break's proposal in the skill's sections (**Root cause**, hypotheses, **Tests not performed**, verdict and why, remediation, control, **End-state validation**), then the **Sign-off checklist** with Agent One Finance's answer beside each question; Frank ticks *yes* on the first three.

> Judgement breaks come back in the skill's own sections: root cause, tests not performed,
> verdict, remediation, end state. Before approving, Frank answers the skill's checklist, with
> what Agent One Finance already knows beside each question.

### 12 · 2:57 — The next COB *(follow-through)*

On screen: yesterday's signed-off run with **Follow-through: 1 cleared · 1 still open** (the MONITOR cleared; the CORRECT & RE-POST did not), then **reopened** leads to today's run, where that break is **U · Adjustment did not clear**, escalated for a person.

> On the next COB every adjustment is re-tested. The timing break cleared. The re-posted swap
> did not, so BO plus adjustments does not equal FO, and the investigation stays open for a
> person.

### 13 · 3:12 — Rates team *(group settings)*

On screen: People (owners and reviewers), then "What this group sets".

> The Rates team runs the same engine and the same playbook, with its own books, thresholds,
> schedule and reviewers. A new team is a configuration file, not a new project.

### 14 · 3:26 — New use cases *(Carol, Authoring)*

On screen: a template is chosen, "Passes every platform check", then **Submit for approval**.

> New work, such as accruals, substantiation or intercompany, starts from a template or a
> requirement, is checked by the platform, and goes live only when a second owner approves it.

### 15 · 3:39 — Run the bank *(Operations)*

On screen: platform health and entitlements, the live tail of system calls, then the off
switches.

> For technology, it is one platform to run. Every data access is checked against entitlements
> and audited. Sensitive data is masked before the model sees it. Costs are capped, and
> anything can be switched off in one click.

### 16 · 3:56 — What it means *(card)*

> So analysts move from investigating to reviewing, one decision covers a whole pattern, and
> every team gets the same features and controls, as configuration rather than new builds.

### 17 · 4:08 — Next steps *(card)*

> We propose a pilot on FOBO Prime and Rates, measuring hours saved against the twelve minute
> basis, then month-end accruals and substantiation. Thank you.

---

**After the video**, put up the time-saving arithmetic with your own volumes. For example,
200 breaks a day × 12 minutes is 40 hours. That is *illustrative*: it is arithmetic on FOBO's
basis, not a measured result. Likely questions and answers are in [`README.md`](README.md).

**To re-record it** (dev stack running: API on :8300, web on :5180):

```bash
cd docs/agent-one-finance/demo
node record-silent.mjs --out /tmp/raw-silent           # 15 clips; ~5 min
python build-silent.py /tmp/raw-silent aof-demo-silent.mp4
```

Two scenes open a case of their own:
- Scene 8 opens `RATES-LDN-01`, COB 2026-09-24.
- Scene 9 opens `RATES-LDN-02`, COB 2026-09-26, and approves it.

To record again on the same database, give them unused keys, for example
`ASK_COB=2026-09-29 SIGNOFF_BOOK=RATES-LDN-03 SIGNOFF_COB=2026-09-24`. To change a line, edit
`silent-scenes.json`; the scene lengths follow the words.
