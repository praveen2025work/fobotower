// The walkthrough a snapshot opens with: two FOBO tasks and a day of FI Credit books,
// explained step by step, each step able to open the part of the screen it talks about.
// Written for the tasks in this recording (COB 20 October 2026); task ids are stable for
// a book, COB and group.

export interface Target {
  route: string;          // the page, e.g. /tasks/<id>, or /agents/<id>?tab=summary
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

const BREAKS = "/tasks/break.investigation.8b88909bb786";
const BREAKS_YESTERDAY = "/tasks/break.investigation.bb1aad48b02d";
const REC = "/tasks/recon.investigation.65bc19fe320f";

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
          show: { route: "/agents/recon.investigation/groups/cats-motif-rates" },
        },
      ],
    },
  ],
  outro: [
    "Month-end accruals is included as configuration only (Agents → Month-end accruals).",
  ],
};
