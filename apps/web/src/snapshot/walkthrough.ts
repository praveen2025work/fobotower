// The walkthrough a snapshot opens with: two FOBO examples explained step by step, each
// step able to open the part of the screen it talks about. Written for the tasks in this
// recording (COB 20 October 2026); task ids are stable for a key (a book, or a FOBO group
// and region) with its COB and group.

export interface Target {
  route: string;          // the page, e.g. /tasks/<id> or /agents/<id>/groups/<group>
  tab?: string;           // a tab to open on it, by its name
  proposal?: string;      // a proposal to select in a task, by the start of its label
  highlight?: string;     // text to point at once there
}

// A paragraph, or a list of points. **Bold** marks what the screen shows, `code` a configuration or event field.
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
const RATES_EMEA = "/tasks/recon.investigation.ec76a453e8fe";
const RATES_EMEA_YESTERDAY = "/tasks/recon.investigation.57f816f79cb1";
const RATES_APAC = "/tasks/recon.investigation.a7b2e1297686";

export const WALKTHROUGH: { title: string; intro: Block[]; examples: Example[]; outro: Block[] } = {
  title: "FOBO on two agents, step by step",
  intro: [
    "**Balance Recon Agent** investigates the breaks MB Rec's balance reconciliation leaves open. **Helix FOBO Agent** reconciles CATS to MOTIF itself: here one task per FOBO group, region and COB, opened by FOBO's feed — Rates and FI Credit, each in EMEA, APAC and the Americas.",
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
      title: "Helix FOBO Agent: Rates EMEA, one task for 300 books",
      subtitle: "FOBO's feed sends one event per group, region and COB; each opens one task that reconciles every book of that region.",
      steps: [
        {
          title: "Three events, three Rates tasks",
          body: [
            "When FOBO's CSV for a group and region has loaded, its feed sends one event: `{ group: 500081, group_name: Rates, region: EMEA, cob: 2026-10-20 }`. Rates EMEA, Rates APAC and Rates AMER are three events and three tasks; FI Credit has its own three.",
            "The task is named from the reference data, which knows group 500081 as Rates. Each region has its own breaks, proposals, sign-off and Summary, and only that region's controllers see it.",
          ],
          show: { route: RATES_EMEA, highlight: "Rates EMEA · COB 2026-10-20" },
        },
        {
          title: "The Summary: what it read and found",
          body: [
            "A regional task opens on its **Summary**. AOF read 2,796 CATS and 2,755 MOTIF positions for the 300 Rates EMEA books and matched them by book and instrument.",
            "216 breaks in 149 books; the other 151 books reconciled clean. The tiles show the gross and net amount and how many breaks are still to decide.",
          ],
          show: { route: RATES_EMEA, tab: "Summary", highlight: "300 books" },
        },
        {
          title: "By desk, then product, then book",
          body: [
            "The group sets `task.summarize_by: [book_desk, book_product, book]`; the `resolve` step looks up each break's desk and product in the reference data, as of the COB.",
            "Open a desk to see its products, a product to see its books. Each row shows its breaks, amounts, what is still open and which proposals its breaks are in.",
          ],
          show: { route: RATES_EMEA, tab: "Summary", highlight: "By book desk" },
        },
        {
          title: "Proposals across the books",
          body: [
            "The playbook groups breaks by category and side across the whole region, so one decision covers every book with the same cause:",
            [
              "**Settlement break · back office**: 128 breaks in 122 books, MOTIF holding two entries with the same settlement reference. The verdict table says POST, but some of the 128 fail validation tests FO-1 and FO-2, so the playbook holds the POST and **escalates** the group to Operations.",
              "**Trade booking break · front office**: 21 breaks in 19 books waiting for desk confirmation. **DO NOT POST**. Owner: Desk.",
              "**Data quality break · back office**: 16 breaks in 15 books whose instrument does not resolve in MOTIF static data. **DO NOT POST**. Owner: Technology.",
              "**Novel break**: 7 breaks no cause check explains. The model read the region's booking events and **escalated** them to Product Control.",
            ],
            "Where the side is not proven, the model writes a proposal without a verdict and the controller decides. Click a proposal to open it with its breaks.",
          ],
          show: { route: RATES_EMEA, tab: "Summary", highlight: "Proposals across" },
        },
        {
          title: "The model session",
          body: [
            "**Model session** on the Summary says who proposed what: the playbook settled six proposals and the model reasoned three. For the model's proposals it shows the adapter and model, tokens, cost and turns as the adapter reports them, against the agent's cost limit, and every lookup it made.",
            "The model is offered `motif.group_booking_events`, scoped to the task's FOBO group and region, and a **booking-events** specialist it can hand the trawl to. In this snapshot the model is a fixed stand-in that reports no usage; in the office the same card shows the real model's figures.",
          ],
          show: { route: RATES_EMEA, tab: "Summary", highlight: "Model session" },
        },
        {
          title: "Each region is its own task",
          body: [
            "Rates APAC is a separate task with its own Summary: Hana, the Rates APAC controller, has signed it off. Rates EMEA waits for Rita, Rates AMER for Raj.",
          ],
          show: { route: RATES_APAC, tab: "Summary" },
        },
        {
          title: "Signed off",
          body: [
            "Yesterday's Rates EMEA task is signed off: every proposal decided, escalations raised as tickets for the owning teams, and its record, Excel export and evidence pack kept.",
          ],
          show: { route: RATES_EMEA_YESTERDAY, tab: "Summary" },
        },
        {
          title: "The configuration behind it",
          body: [
            "The **CATS vs MOTIF — by FOBO group and region** group sets the key (`group`, `region`, `cob`), the data scopes (FOBO group and region), the regional CATS and MOTIF reads, the playbook and the reviewers. Every change is a new version that another owner approves.",
          ],
          show: { route: "/agents/recon.investigation/groups/cats-vs-motif" },
        },
      ],
    },
  ],
  outro: [
    "Month-end accruals is included as configuration only (Agents → Month-end accruals).",
  ],
};
