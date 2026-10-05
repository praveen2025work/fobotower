// The orchestrator, stage by stage: what each step does, the settings that
// belong to it, and how a problem the server reports is filed under it.
// The editor renders this description; adding a setting is one entry here.

import type { FieldSpec, Opt } from "./fields";
import { get, setPath, type Json } from "./paths";

export interface Stage {
  id: string;
  title: string;
  /** What it does, in a sentence a business owner reads. */
  says: string;
  /** The workflow step(s) this stage configures; none = case-wide settings. */
  step?: string;
  /** May the step be switched off? (gates and the item source may not.) */
  optional?: boolean;
  gate?: boolean;
  /** What switching the step on adds, when its section is missing. */
  onEnable?: (m: Json) => Json;
  /** What switching it off clears (a section without its step is refused). */
  clears?: { path: string; value: unknown }[];
  fields: FieldSpec[];
  /** Server problems that belong here. */
  owns: RegExp;
  /** Shown only to a capability's own owners (never a group's to set). */
  capabilityOnly?: boolean;
}

const keyFields = (m: Json): Opt[] => ((get(m, "case.key") as string[]) ?? []).map((k) => ({ value: k }));
const categories = (m: Json): Opt[] =>
  Object.entries((get(m, "playbook.categories") as Record<string, { name?: string }>) ?? {}).map(([k, c]) => ({ value: k, label: `${k} · ${c.name ?? ""}` }));
const sides = (m: Json): Opt[] => [...((get(m, "playbook.sides") as string[]) ?? []), "UNKNOWN"].map((s) => ({ value: s }));
const VERDICTS: Opt[] = ["POST", "DO_NOT_POST", "ESCALATE", "CORRECT_AND_REPOST"].map((v) => ({ value: v, label: v.replace(/_/g, " ") }));
const verdictOptions = (m: Json): Opt[] => {
  const used = Object.values((get(m, "playbook.verdicts") as Record<string, Record<string, string>>) ?? {}).flatMap((r) => Object.values(r));
  return [...new Set([...VERDICTS.map((v) => v.value), ...used])].map((v) => ({ value: v, label: v.replace(/_/g, " ") }));
};
const hasPlaybook = (m: Json) => !!get(m, "playbook");

export const STAGES: Stage[] = [
  {
    id: "case",
    title: "Start: what a case is",
    says: "What one unit of work is, who can see it, when it opens on its own, and when it is due.",
    owns: /^case\.|case\.(key|scopes|schedule|opens_as|due)|scheduled/,
    fields: [
      { kind: "text", path: "case.label", label: "A case is called", placeholder: "Rec run" },
      { kind: "text", path: "case.item_label", label: "An item is called", placeholder: "Break" },
      { kind: "list", path: "case.key", label: "A case is identified by", help: "The fields that make one case, e.g. book, cob." },
      { kind: "template", path: "case.subject", label: "Case title", help: "A template over the key, e.g. {book} · COB {cob}." },
      { kind: "kv", path: "case.scopes", label: "Data scope checks", keyLabel: "Key field", valueLabel: "Entitlement scope", help: "Who may see a case: each key field is checked against the person's data scope." },
      { kind: "select", path: "case.opens_on", label: "Opens", options: [
        { value: "manual", label: "When someone opens it" }, { value: "api", label: "When a system calls the API" },
        { value: "schedule", label: "On a schedule" }, { value: "event", label: "When an event arrives" }] },
      { kind: "cron", path: "case.schedule", label: "Schedule (cron: minute hour day month weekday)", placeholder: "30 6 * * 1-5", help: "30 6 * * 1-5 = 06:30 every business day.", when: (m) => get(m, "case.opens_on") === "schedule" },
      { kind: "rows", path: "case.schedule_keys", label: "Cases each run opens", addLabel: "Add a case", newRow: {},
        help: "One row per case. Dates may use {prev_business_day}, {yesterday}, {today}, {prev_month}, {this_month}.",
        when: (m) => get(m, "case.opens_on") === "schedule",
        columns: (m) => keyFields(m).map((k) => ({ key: k.value, label: k.value, wide: true })) },
      { kind: "bool", path: "case.events", label: "Other systems may open cases (POST /api/events)" },
      { kind: "text", path: "case.opens_as", label: "Scheduled and event cases run as", placeholder: "helix-scheduler", help: "A service user with the roles and data scopes those cases need." },
      { kind: "object", path: "case.due", label: "Deadline", toggle: "Cases have a deadline", empty: { from: "opened", business_days: 1, hours: 0, at: null, warn_hours: 2 },
        fields: [
          { kind: "select", path: "from", label: "Counted from", options: (m) => [{ value: "opened", label: "when it opened" }, ...keyFields(m)] },
          { kind: "number", path: "business_days", label: "Business days after", min: 0, max: 60 },
          { kind: "time", path: "at", label: "At (time of day)" },
          { kind: "number", path: "warn_hours", label: "Warn this many hours before", min: 0, max: 72 },
        ] },
    ],
  },
  {
    id: "thresholds",
    title: "Thresholds",
    says: "Named values the rules, tests and verdicts use. Leave a value empty until it is confirmed: anything that depends on it is flagged for confirmation, never assumed.",
    owns: /^policy|is not a policy/,
    fields: [{ kind: "policy", path: "policy", label: "Thresholds" }],
  },
  {
    id: "source",
    title: "Get the items",
    says: "Where the items come from: one system (load), or two systems matched to each other (match).",
    owns: /^items\.|^match|step `(load|match)`|`load` or `match`/,
    fields: [
      { kind: "tool", path: "match.left.tool", label: "Left side", access: "read", when: (m) => !!get(m, "match") },
      { kind: "kv", path: "match.left.args", label: "Left side arguments", keyLabel: "Argument", valueLabel: "Value ($case.<field> from the key)", when: (m) => !!get(m, "match") },
      { kind: "tool", path: "match.right.tool", label: "Right side", access: "read", when: (m) => !!get(m, "match") },
      { kind: "kv", path: "match.right.args", label: "Right side arguments", keyLabel: "Argument", valueLabel: "Value ($case.<field> from the key)", when: (m) => !!get(m, "match") },
      { kind: "list", path: "match.keys", label: "Match on", when: (m) => !!get(m, "match") },
      { kind: "text", path: "match.amount_field", label: "Amount compared", when: (m) => !!get(m, "match") },
      { kind: "number", path: "match.tolerance", label: "Tolerance (differences up to this are not breaks)", min: 0, when: (m) => !!get(m, "match") },
      { kind: "text", path: "match.left_label", label: "Left side is called", when: (m) => !!get(m, "match") },
      { kind: "text", path: "match.right_label", label: "Right side is called", when: (m) => !!get(m, "match") },
      { kind: "tool", path: "items.load.tool", label: "Load from", access: "read", when: (m) => !get(m, "match") },
      { kind: "kv", path: "items.load.args", label: "Arguments", keyLabel: "Argument", valueLabel: "Value ($case.<field> from the key)", when: (m) => !get(m, "match") },
      { kind: "text", path: "items.id_field", label: "Item id field" },
      { kind: "text", path: "items.amount_field", label: "Amount field" },
      { kind: "text", path: "items.amount_unit", label: "Amount unit", placeholder: "GBP" },
      { kind: "list", path: "items.display", label: "Columns shown to reviewers" },
      { kind: "expr", path: "items.in_scope", label: "In scope when", help: "Items outside this are kept but not worked, e.g. abs(difference) >= policy.materiality_threshold." },
    ],
  },
  {
    id: "compare", step: "compare", optional: true,
    title: "Compare to a baseline",
    says: "Adds the difference between a measure and its baseline (e.g. actual vs budget) to every item.",
    owns: /^compare|step `compare`/,
    onEnable: (m) => (get(m, "compare") ? m : setPath(m, "compare", { measure: "actual", baseline: "budget", as: "variance" })),
    clears: [{ path: "compare", value: null }],
    fields: [
      { kind: "text", path: "compare.measure", label: "Measure" },
      { kind: "text", path: "compare.baseline", label: "Baseline" },
      { kind: "text", path: "compare.as", label: "Store the difference as" },
    ],
  },
  {
    id: "enrich", step: "enrich", optional: true,
    title: "Enrich",
    says: "Reads more data for each case (e.g. dated snapshots) and joins it onto the items.",
    owns: /^enrich|`enrich`/,
    clears: [{ path: "enrich", value: [] }],
    fields: [{ kind: "rows", path: "enrich", label: "Reads", addLabel: "Add a read", newRow: { tool: "", args: {}, keys: [], prefix: "" },
      columns: [{ key: "tool", label: "Tool", kind: "tool", access: "read" }, { key: "args", label: "Arguments", kind: "args" }, { key: "keys", label: "Join on", kind: "list" }, { key: "prefix", label: "Field prefix" }] }],
  },
  {
    id: "resolve", step: "resolve", optional: true,
    title: "Reference lookups",
    says: "Looks up reference data for each item in the knowledge graph, as of the business date — e.g. which desk owned a book on the COB.",
    owns: /^resolve|knowledge\.(reference|as_of)|`resolve`/,
    clears: [{ path: "resolve", value: [] }],
    fields: [
      { kind: "text", path: "knowledge.reference", label: "Reference data", placeholder: "fobo-reference", help: "The reference file (config/helix/knowledge/<name>.yaml)." },
      { kind: "select", path: "knowledge.as_of", label: "Read as of", options: keyFields, nullable: true },
      { kind: "rows", path: "resolve", label: "Lookups", addLabel: "Add a lookup", newRow: { node: "", path: [], as: "", take: "name" },
        columns: [{ key: "node", label: "Start at", wide: true }, { key: "path", label: "Follow", kind: "list" }, { key: "as", label: "Store as" }, { key: "take", label: "Take" }] },
    ],
  },
  {
    id: "classify", step: "classify", optional: true,
    title: "Playbook: checks and verdicts",
    says: "The business's rules, run on every item before any model: cause checks (all run, negatives kept), categories, the verdict table, and guards no one can override.",
    owns: /^playbook|playbook|`classify`/,
    clears: [{ path: "playbook", value: null }],
    onEnable: (m) => (get(m, "playbook") ? m : setPath(m, "playbook", { categories: {}, default_category: "", sides: ["FO", "BO"], checks: [], verdicts: {}, guards: [] })),
    fields: [
      { kind: "rows", path: "playbook.checks", label: "Cause checks", addLabel: "Add a check", when: hasPlaybook,
        help: "Each check is an expression over one item; the first positive check in this order is the cause.",
        newRow: { id: "", when: "", category: "", side: "UNKNOWN", reason: "" },
        columns: [{ key: "id", label: "Id" }, { key: "when", label: "Positive when", kind: "expr", wide: true },
          { key: "category", label: "Category", kind: "select", options: categories }, { key: "side", label: "Side", kind: "select", options: sides },
          { key: "reason", label: "Reviewer wording", wide: true }] },
      { kind: "dict", path: "playbook.categories", label: "Categories", keyLabel: "Code", addLabel: "Add a category", when: hasPlaybook,
        newEntry: { name: "", determinism: "deterministic", escalate_to: "" },
        columns: [{ key: "name", label: "Name", wide: true },
          { key: "determinism", label: "Settled by", kind: "select", options: [{ value: "deterministic", label: "the verdict table" }, { value: "judgement", label: "a person (judgement)" }] },
          { key: "escalate_to", label: "Owning team" }] },
      { kind: "select", path: "playbook.default_category", label: "When no check is positive", options: categories, when: hasPlaybook },
      { kind: "list", path: "playbook.sides", label: "Proven sides", when: hasPlaybook, help: "A side not listed (or UNKNOWN) is never settled by the table." },
      { kind: "matrix", path: "playbook.verdicts", label: "Verdict table (category × side)", rows: "playbook.categories", cols: "playbook.sides", options: verdictOptions, when: hasPlaybook },
      { kind: "rows", path: "playbook.guards", label: "Guards (applied after the table and after the model)", addLabel: "Add a guard", when: hasPlaybook,
        newRow: { verdict: "POST", when: "", instead: "ESCALATE", reason: "" },
        columns: [{ key: "verdict", label: "Never", kind: "select", options: VERDICTS }, { key: "when", label: "When", kind: "expr", wide: true },
          { key: "instead", label: "Instead", kind: "select", options: VERDICTS }, { key: "reason", label: "Why", wide: true }] },
      { kind: "multi", path: "playbook.confirm_verdicts", label: "Verdicts that need a confirmed threshold", options: VERDICTS, when: hasPlaybook },
      { kind: "multi", path: "playbook.verdict_policy", label: "…these thresholds", when: hasPlaybook,
        options: (m) => Object.keys((get(m, "policy") as Json) ?? {}).map((k) => ({ value: k, label: k.replace(/_/g, " ") })) },
      { kind: "rows", path: "playbook.tests", label: "Validation tests", addLabel: "Add a test", when: hasPlaybook,
        help: "Every test runs on every item: pass, fail, or not run (evidence missing or threshold unset) — never passed by default.",
        newRow: { id: "", side: "FO", validates: "", check: "", fails_when: "", needs: [], policy: [], blocks_post: false, on_fail: "" },
        columns: [{ key: "id", label: "Id" }, { key: "side", label: "Side" }, { key: "check", label: "Checks", wide: true },
          { key: "fails_when", label: "Fails when", kind: "expr", wide: true }, { key: "needs", label: "Needs fields", kind: "list" },
          { key: "blocks_post", label: "Holds a POST", kind: "bool" }, { key: "on_fail", label: "On fail", wide: true }] },
      { kind: "template", path: "playbook.comment", label: "Finding wording", help: "e.g. {category_name} ({side}): {reasons}.", when: hasPlaybook },
      { kind: "kv", path: "playbook.side_names", label: "Side names", keyLabel: "Side", valueLabel: "Called", when: hasPlaybook },
    ],
  },
  {
    id: "group", step: "group",
    title: "Group",
    says: "Collapses items into groups so one decision covers many — e.g. by category and side.",
    owns: /^group_by|^group_label/,
    fields: [
      { kind: "list", path: "group_by", label: "Group by", help: "Item fields; empty = one group per case." },
      { kind: "template", path: "group_label", label: "Group name", help: "e.g. {category_name} · {side_name}." },
    ],
  },
  {
    id: "reason", step: "reason",
    title: "Rules, then the model",
    says: "Rules settle what they can; the rest goes to the model with only the tools listed here — or straight to people.",
    owns: /^rules|^reasoning|rules\[|^limits/,
    fields: [
      { kind: "rows", path: "rules", label: "Rules (run first, in order)", addLabel: "Add a rule",
        newRow: { id: "", when: "", then: { status: "proposed", comment: "" } },
        columns: [{ key: "id", label: "Id" }, { key: "when", label: "When", kind: "expr", wide: true },
          { key: "then.status", label: "Then", kind: "select", options: [{ value: "proposed", label: "propose" }, { value: "escalated", label: "escalate" }] },
          { key: "then.comment", label: "Wording", wide: true }] },
      { kind: "select", path: "reasoning.reasoner", label: "What the rules cannot settle goes to", options: [{ value: "llm", label: "the model, then a person" }, { value: "none", label: "a person (no model)" }] },
      { kind: "select", path: "reasoning.output", label: "The model writes", options: [{ value: "verdict", label: "a verdict" }, { value: "commentary", label: "commentary" }, { value: "classification", label: "a classification" }], when: (m) => get(m, "reasoning.reasoner") === "llm" },
      { kind: "tools", path: "reasoning.tools", label: "Tools the model may call (read only)", access: "read", when: (m) => get(m, "reasoning.reasoner") === "llm" },
      { kind: "textarea", path: "reasoning.skill", label: "Instructions to the model", when: (m) => get(m, "reasoning.reasoner") === "llm" },
      { kind: "rows", path: "reasoning.specialists", label: "Specialists (subagents)", addLabel: "Add a specialist", when: (m) => get(m, "reasoning.reasoner") === "llm",
        newRow: { name: "", description: "", instructions: "", tools: [] },
        columns: [{ key: "name", label: "Name" }, { key: "description", label: "When to use it", wide: true }, { key: "instructions", label: "Instructions", kind: "textarea", wide: true }, { key: "tools", label: "Tools (from the model's)", kind: "tools", within: "reasoning.tools" }] },
      { kind: "number", path: "limits.max_cost_usd_per_case", label: "Model spend cap per case (USD)", min: 0, nullable: true, when: (m) => get(m, "reasoning.reasoner") === "llm" },
      { kind: "number", path: "limits.max_cost_usd_per_day", label: "Model spend cap per day (USD)", min: 0, nullable: true, when: (m) => get(m, "reasoning.reasoner") === "llm" },
    ],
  },
  {
    id: "draft", step: "draft",
    title: "Draft",
    says: "Writes the case summary a reviewer reads first: what is in scope, what was proposed, what was escalated.",
    owns: /^draft/,
    fields: [{ kind: "number", path: "metrics.manual_minutes_per_item", label: "Manual minutes per item (for hours saved)", min: 1, help: "The declared basis for the efficiency figures; shown next to them." }],
  },
  {
    id: "validate", step: "validate", gate: true,
    title: "Validate figures",
    says: "Every figure the model states must trace to the case's data or a tool result; anything that does not is escalated to a person. Always on.",
    owns: /^validate/,
    fields: [],
  },
  {
    id: "review", step: "review", gate: true,
    title: "Human review",
    says: "People decide every group. The run always stops here until they do.",
    owns: /^review/,
    fields: [
      { kind: "list", path: "review.roles", label: "Reviewers (roles)" },
      { kind: "multi", path: "review.require_comment", label: "The reviewer must explain", options: [{ value: "reject", label: "a rejection" }, { value: "escalated", label: "approving an escalated group" }] },
      { kind: "select", path: "review.confirm", label: "Approving a verdict that needs confirmation takes", options: [
        { value: "tick_and_comment", label: "a tick and the reviewer's words" }, { value: "tick", label: "a tick" }, { value: "none", label: "nothing extra" }] },
      { kind: "multi", path: "review.bulk_exclude", label: "“Approve all” leaves for one-by-one review", options: [
        { value: "confirmation", label: "verdicts needing confirmation" }, { value: "judgement", label: "judgement calls" },
        { value: "escalated", label: "escalated groups" }, { value: "model", label: "anything the model proposed" }] },
      { kind: "expr", path: "review.dual_review_when", label: "Two approvers when", placeholder: "abs(total) > 1000000", help: "Over a group: total, count, its key fields, policy." },
      { kind: "number", path: "review.max_reinvestigations", label: "Times a group may be sent back", min: 0, max: 10 },
      { kind: "bool", path: "review.opener_may_decide", label: "Whoever opened a case may also sign it off" },
      { kind: "bool", path: "review.allow_delegation", label: "Reviewers may hand their reviews to a colleague while away" },
    ],
  },
  {
    id: "record", step: "record", gate: true,
    title: "Record, tickets and follow-up",
    says: "Records each decision so the next run learns from it, raises tickets for owning teams, and keeps what reviewers need next time. Always on.",
    owns: /^knowledge\.(entities|priors)|^escalation|^insights|^export|^retention|`escalation`/,
    fields: [
      { kind: "list", path: "knowledge.entities", label: "Learn across", help: "Fields that link a decision to what it concerns (e.g. instrument, book), so related groups learn from it." },
      { kind: "number", path: "knowledge.priors_lookback_days", label: "Learn from decisions of the last (days)", min: 1, nullable: true },
      { kind: "object", path: "escalation", label: "Tickets for owning teams", toggle: "Raise a ticket after the decision",
        empty: { tool: "", when: "action == 'approve' and status == 'escalated'", args: {} },
        fields: [
          { kind: "tool", path: "tool", label: "Ticketing tool", access: "write" },
          { kind: "expr", path: "when", label: "Raise when" },
          { kind: "kv", path: "args", label: "Ticket fields", keyLabel: "Field", valueLabel: "Value ({escalate_to}, {subject}, {label}, {comment}…)" },
        ] },
      { kind: "object", path: "insights.recurring", label: "Recurring items", toggle: "Show items that keep coming back",
        empty: { same: [], lookback_cases: 10, min_runs: 2 },
        fields: [
          { kind: "list", path: "same", label: "In earlier cases with the same" },
          { kind: "number", path: "lookback_cases", label: "Look back over (cases)", min: 1, max: 100 },
          { kind: "number", path: "min_runs", label: "Seen in at least (runs)", min: 2, max: 100 },
        ] },
      { kind: "list", path: "export.columns", label: "Excel download columns", help: "Empty = the columns shown to reviewers." },
      { kind: "object", path: "retention", label: "Retention", toggle: "Delete finished cases after a period (legal hold aside)", empty: { days: 2555 },
        fields: [{ kind: "number", path: "days", label: "Keep for (days)", min: 1 }] },
    ],
  },
  {
    id: "publish", step: "publish", optional: true,
    title: "Write back",
    says: "Writes approved results to a bank system — only after a second person, who did not review, releases it.",
    owns: /^publish|`publish`/,
    clears: [{ path: "publish", value: null }],
    onEnable: (m) => {
      let out = get(m, "publish") ? m : setPath(m, "publish", { tool: "", per: "group", args: {}, approver_roles: [] });
      const pause = (get(out, "pause_before") as string[]) ?? [];
      if (!pause.includes("publish")) out = setPath(out, "pause_before", [...pause, "publish"]);
      return out;
    },
    fields: [
      { kind: "tool", path: "publish.tool", label: "Write with", access: "write" },
      { kind: "select", path: "publish.per", label: "One write per", options: [{ value: "group", label: "approved group" }, { value: "case", label: "case (one report)" }] },
      { kind: "kv", path: "publish.args", label: "Arguments", keyLabel: "Argument", valueLabel: "Value ($comment, $group.<field>, $approved…)" },
      { kind: "list", path: "publish.approver_roles", label: "Released by (roles)" },
    ],
  },
  {
    id: "owners", capabilityOnly: true,
    title: "Owners and team settings",
    says: "Who may change this capability (four-eyes: the drafter cannot approve), and what each team group may set for itself.",
    owns: /^owners|^configurable|cannot be set by a group/,
    fields: [
      { kind: "list", path: "owners.people", label: "Owners (people)" },
      { kind: "text", path: "owners.role", label: "Owners (role)" },
      { kind: "bool", path: "owners.four_eyes", label: "Four-eyes: a change needs a second owner" },
      { kind: "list", path: "configurable", label: "Team groups may set", help: "Dotted paths; x.* = anything under x. The workflow, gates, write-back and ownership always stay here." },
    ],
  },
];

/** Steps in the engine's order (load and match are the item source). */
export const STEP_ORDER = ["load", "match", "enrich", "resolve", "classify", "compare", "group", "reason", "draft", "validate", "review", "record", "publish"];

/** The stage a server problem belongs to (the first that owns it). */
export function stageOf(problem: string): string {
  if (/required|gates must|must be the last|must pause|must come right after|needs .* produced by no earlier|listed twice|unknown step/.test(problem)) return "pipeline";
  return STAGES.find((s) => s.owns.test(problem))?.id ?? "pipeline";
}
