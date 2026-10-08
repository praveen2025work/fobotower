# UI principles: show the next decision, fold the rest

**Date:** 2026-10-08 · applies to every screen of the console (`apps/web`)

The console helps a person do one thing at a time. Every screen answers "what do I do next?" first,
and keeps everything else one click away.

1. **One question per screen.** Overview: what is waiting on me. Inbox: which case next. Case: which
   group, and approve or reject. Capability: its cases. Lead with that; nothing above it competes.
2. **Fold what is reference, not decision.** Use `Fold` (`components/ui.tsx`) with a `summary` so a
   closed section still says what it holds ("Data used · 5 system calls"). Folded by default:
   - case: Case details (key, workflow, write-back, follow-through, data sets, evidence, questions,
     case record), Data used, Ask the model to look again;
   - overview: Impact (hours saved, escalations, platform counts);
   - capability: the workflow (one line and a link), "Open a run", Data and parameters.
3. **Remember what each person opens.** `useRemembered` keeps a fold open or closed per browser
   (`aof.fold.*`). It is a convenience only; the page works without it.
4. **Say it once.** A number or a status appears in one place. No stat card repeats the headline; no
   panel repeats the title (the case key is in the title, not again in a side panel).
5. **One flag, not five.** A row shows what is left ("2 of 3 to decide") and the one flag that matters
   most (escalated, then to confirm, then judgement); the rest is in the tooltip.
6. **Hide what is empty.** A field with no value is not shown (no "Category ·" or "Owner —").
7. **Technical detail is for those who ask.** Step ids, versions, trace ids and tool names live in
   Case details, Run history, Model session and Configure, never on the first view.
8. **Actions over explanations.** One line of guidance where a person must act ("Approve with your own
   explanation, reject with a reason, or ask the model to look again"), not a list of rules.

New panels start folded unless the person needs them for the decision on that screen.
