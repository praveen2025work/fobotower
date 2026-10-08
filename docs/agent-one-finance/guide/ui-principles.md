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

9. **Five colours, five meanings.** Colour says what to do, never decorates:

   | Meaning | Family | Used for |
   |---|---|---|
   | Neutral | `surface` (grey) | most text, borders, statuses that need nothing ("proposed", "confirmed") |
   | Your turn, brand | `primary`, `accent`, `brand` (Barclays blue, cyan) | links, buttons, "awaiting review", tollgates, "Your review" |
   | Needs a person's judgement | `orange` | escalated, to confirm, judgement call, due soon |
   | Problem | `red` | failed, rejected, refused, overdue |
   | Done | `green` | approved, completed, published |

   `npm run check:styles` fails on any other colour family (yellow, amber, purple, sky, …): they carry
   no meaning and have no dark-mode version in the Barclays theme. In lists, an urgency is coloured text,
   not a filled badge, so one red row still stands out.

10. **Configuration in the order a person thinks.** The editor groups steps as The case, Data,
    Decide, People and gates, Ownership; steps not in use are listed last. A long list of things
    (prepare-data steps, tools) shows what is chosen, one line each, and opens or adds on demand.

11. **Say it once.** A message appears in one place: the case header does not repeat what "Your
    review" says, an escalated group shows one escalation card (not also a judgement strip), a step's
    description does not repeat its gate note, and a list chip does not repeat the title.

12. **Everyday first, the rest under "More options".** A step's settings that most capabilities
    never change (authority tiers, reserved decisions, who to ask for evidence, reminders) sit in a
    "More options" fold whose summary says how many are in use, so nothing is hidden silently.

13. **Long forms are short steps.** Authoring asks four short steps (The work, Case and data, Who
    decides, Checks) with Back and Next; "Build now" works from any step and the platform's check
    says what is missing.

14. **Plain words for time and things.** "15 days overdue", not "Overdue 15 days ago"; "1 break",
    "3 breaks", not "break(s)"; names, not ids ("Break investigation", not `break.investigation`).

15. **One card for the decision.** On a case, "Your review" is one line, and the model's finding
    is one card: why a person decides (when escalated), the verdict, then the reasoning.

16. **Empty for a reason, said once.** Platform support holds no data scope, so Operations and
    Audit show who the case data belongs to and what support can do instead (health, connectors,
    off switches, Phoenix), not empty panels.

Every screen, as it is now: `docs/agent-one-finance/demo/agent-one-finance-screens.html` (and `.pdf`).

New panels start folded unless the person needs them for the decision on that screen.
