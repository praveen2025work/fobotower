// The walkthrough a snapshot opens with: two FOBO tasks and a day of FI Credit books,
// explained step by step, each step able to open the part of the screen it talks about.
// Written for the tasks in this recording (COB 20 October 2026); task ids are stable for
// a book, COB and group.

export interface Target {
  route: string;          // the page, e.g. /cases/<id>, or /capabilities/<id>?tab=summary
  tab?: string;           // a tab to open on it, by its name
  proposal?: string;      // a proposal to select in a task, by the start of its label
  highlight?: string;     // text to point at once there
}

// A paragraph, or a list of points. **Bold** marks what the screen shows.
export type Block = string | string[];

export interface Step {
  title: string;
  body: Block[];
  show?: Target;
}

export interface Example {
  title: string;
  subtitle: string;
  steps: Step[];
}

const BREAKS = "/cases/break.investigation.8b88909bb786";
const BREAKS_YESTERDAY = "/cases/break.investigation.bb1aad48b02d";
const REC = "/cases/recon.investigation.65bc19fe320f";
const SUMMARY = "/capabilities/recon.investigation?tab=summary&date=2026-10-20";
const AMERICAS_BOOK = "/cases/recon.investigation.2dcaf3e010f8";     // FI Credit Americas · CDX (FIC-AMER-0385)

export const WALKTHROUGH: { title: string; intro: Block[]; examples: Example[]; outro: Block[] } = {
  title: "FOBO on two agents, step by step",
  intro: [
    "**Balance Recon Agent** investigates the breaks MB Rec's balance reconciliation leaves open. **Helix FOBO Agent** reconciles CATS to MOTIF for every master book: here, the FI Credit books in APAC, EMEA and the Americas, and the Rates and Prime books.",
    "Each step below explains one part; **Show me** opens it on the screen. The snapshot is read-only: you can look at everything, but nothing can be approved or changed.",
  ],
  examples: [
    {
      title: "Balance Recon Agent: Rates futures (RATES-LDN-04)",
      subtitle: "MB Rec has already reconciled CATS to MOTIF; the agent investigates the breaks its rules could not clear.",
      steps: [
        {
          title: "One task per master book and COB",
          body: [
            "MB Rec reconciled CATS to MOTIF for the Rates futures master book and cleared what its rules could. Seven breaks were left open for COB 20 October. They arrive in AOF as one task for the Rates controllers.",
          ],
          show: { route: BREAKS, highlight: "Rates futures (RATES-LDN-04)" },
        },
        {
          title: "What AOF read, and from where",
          body: [
            "Everything comes through the MCP gateway, read-only:",
            ["MB Rec: the open breaks, each one's last five COBs, and the same instruments in other books", "MOTIF: positions, booking events and the FO/BO snapshots the cause checks need", "CATS and MOTIF: the trades behind each break"],
            "Each proposal lists the calls behind it under **Data used**. Every step of the run is in **Run history**, where **as it was** opens what the task held at that point.",
          ],
          show: { route: BREAKS, tab: "Run history" },
        },
        {
          title: "The playbook settles four breaks on its own",
          body: [
            "FOBO's cause checks and verdict table decide these without the model:",
            [
              "**BOBL FUT**: booked after the MOTIF cut-off. **Timing difference → MONITOR**: it should clear on the next COB, and AOF checks that it did.",
              "**EURIBOR FUT Z6**: the front-office trade is waiting for desk confirmation. **DO NOT POST**: a front-office cause is never fixed in MOTIF. Owner: Desk.",
              "**SONIA FUT Z6**: no static data for the instrument in MOTIF. **Data quality → DO NOT POST**. Owner: Technology.",
              "**SOFR FUT H7**: MOTIF rejected the journal. **CORRECT AND RE-POST**. Owner: Operations.",
            ],
          ],
          show: { route: BREAKS, proposal: "Rejected posting" },
        },
        {
          title: "The tollgate: a person checks before the model",
          body: [
            "The run stopped before asking the model anything. Rita, a Rates controller, checked that these were today's open breaks from MB Rec and that the playbook had sorted them right, then let it continue with a note.",
            "In **Run history**, **reason** is the step that waited for her and the row with the people icon is her go-ahead.",
          ],
          show: { route: BREAKS, tab: "Run history", highlight: "input: findings" },
        },
        {
          title: "Three judgement calls for the controller",
          body: [
            "Where the playbook cannot prove which side is wrong, the model reads the trades and booking events and writes a proposal. It never decides.",
            [
              "**EURIBOR FUT H7**: CATS and MOTIF priced from different curves; side not proven. A proposal without a verdict: the controller decides. Owner: Market data.",
              "**SOFR FUT Z6**: in CATS, missing in MOTIF (−676,048.53). **Escalated** to Operations.",
              "**UST 2Y FUT**: MOTIF may hold it under a near-identical name. **Escalated**: confirm the match before anything is booked.",
            ],
            "In this snapshot the model is a fixed stand-in, so its write-ups list what it read and quote yesterday's approved explanation.",
          ],
          show: { route: BREAKS, proposal: "Missing side" },
        },
        {
          title: "The controller signs off each group",
          body: [
            "For every group the controller approves or rejects and answers FOBO's sign-off checklist: what was checked and why, the evidence, the root cause, whether to post, who to engage, and a preventative control. **Approve 4 straightforward** approves the playbook's proposals in one go and leaves out the judgement calls, which are decided one by one.",
          ],
          show: { route: BREAKS, proposal: "Trade booking break", highlight: "What did I check?" },
        },
        {
          title: "After sign-off",
          body: [
            "Approving a DO NOT POST, a re-post or an escalation raises a ticket for the owning team. MONITOR and re-post breaks are checked again on the next COB. The task keeps its record, an Excel export and an evidence pack. Posting approved adjustments to MOTIF through FAS is a production step and is not set up in this demo.",
            "Yesterday's task for the same book is signed off: open it to see the end state.",
          ],
          show: { route: BREAKS_YESTERDAY },
        },
      ],
    },
    {
      title: "Helix FOBO Agent: USD swaps (RATES-LDN-01)",
      subtitle: "Here the agent matches CATS to MOTIF itself, one task per master book and COB.",
      steps: [
        {
          title: "AOF does the matching",
          body: [
            "AOF reads CATS (front office) and MOTIF (back office) positions for the USD swaps book and compares them instrument by instrument, with a 0.50 tolerance. Three instruments differ.",
          ],
          show: { route: REC, highlight: "USD swaps (RATES-LDN-01)" },
        },
        {
          title: "The same playbook sorts the breaks",
          body: [
            "**IRS 5Y USD**: MOTIF holds two entries with the same settlement reference. **Settlement break → POST**: adjust MOTIF. Owner: Operations.",
          ],
          show: { route: REC, proposal: "Settlement break" },
        },
        {
          title: "The model where the rules stop",
          body: [
            [
              "**SOFR OIS 1Y**: a fee or funding amount on one side only. A trade booking break, but the side is not proven, so there is no verdict: the controller decides. Owner: Desk.",
              "**IRS 2Y USD**: 85,216.04 that no cause check explains. **Novel break → escalated** to Product Control.",
            ],
          ],
          show: { route: REC, proposal: "Novel break" },
        },
        {
          title: "The configuration behind it",
          body: [
            "The **CATS vs MOTIF — Rates** group sets the sources, keys, tolerance, playbook and reviewers for these books. Every change is a new version that another owner approves; the history is under **Versions**.",
          ],
          show: { route: "/capabilities/recon.investigation/groups/cats-motif-rates" },
        },
      ],
    },
    {
      title: "Helix FOBO Agent: a day of 1,240 FI Credit books",
      subtitle: "A task per master book is too many to open one by one. The Summary shows the day by region, desk and product, and decides the same break across many books once.",
      steps: [
        {
          title: "The day at a glance",
          body: [
            "COB 20 October is **1,258 tasks** for this agent: 1,240 FI Credit books in APAC, EMEA and the Americas, 12 Prime and 6 Rates. 794 reconciled clean (CATS and MOTIF agree on every position), 203 are signed off and 261 wait for review.",
          ],
          show: { route: SUMMARY, highlight: "waiting for review" },
        },
        {
          title: "By region, then desk and product",
          body: [
            "Group by **Region**: APAC is signed off (its controllers start first), EMEA is part way, the Americas has not started. Click a region to see its desks, then a desk to see its products; the chip above the table goes back.",
            "Business, region, desk and product come from the reference data, as the task titles do.",
          ],
          show: { route: SUMMARY, tab: "Region" },
        },
        {
          title: "The same break across many books",
          body: [
            "Each row is one proposal found in many books:",
            [
              "**APAC**: MOTIF loaded a settlement batch twice. **Settlement break → POST** in 92 books, approved once by Mei from here; the rest of APAC was then decided book by book.",
              "**EMEA**: a new GBP issue is not in MOTIF static data yet. **Data quality break → DO NOT POST** in 91 books, approved once by Lars, with a Technology ticket for each book.",
              "**The Americas**: the same settlement problem in **155 books**, still to approve. The top row counts them with EMEA's own settlement breaks; click **Americas** in the table above to see its books alone.",
            ],
          ],
          show: { route: SUMMARY, highlight: "The same break across many books" },
        },
        {
          title: "Approve once, checked in every task",
          body: [
            "**Approve** asks for one explanation and a tick that the pattern is the same everywhere. Each task then checks the decision as its own Approve would: judgement calls (a side not proven) and anything else held for one-by-one review stay open, and the result says how many and why.",
          ],
          show: { route: SUMMARY, highlight: "Approve " },
        },
        {
          title: "Every row is a full task",
          body: [
            "This Americas CDX book has the settlement break (POST), a trade booking break the desk must fix (DO NOT POST) and one judgement call. The snapshot holds one book per region in full; the others open in the live console.",
          ],
          show: { route: AMERICAS_BOOK, proposal: "Settlement break" },
        },
        {
          title: "The inbox stays short",
          body: [
            "The 260 FI Credit books still waiting are one inbox row, which opens this summary. The examples above stay as rows of their own.",
          ],
          show: { route: "/inbox", highlight: "Work them by region, desk or pattern" },
        },
        {
          title: "Configured once for every book",
          body: [
            "The **CATS vs MOTIF — FI Credit** group: MOTIF's end-of-day feed opens a task for each book (there is no list of books to keep), the same FOBO playbook sorts the breaks, FI Credit controllers sign off, and **The Summary groups a day's tasks by** names business, region, desk and product.",
          ],
          show: { route: "/capabilities/recon.investigation/groups/cats-motif-fi-credit" },
        },
      ],
    },
  ],
  outro: [
    "Month-end accruals is included as configuration only (Agents → Month-end accruals).",
  ],
};
