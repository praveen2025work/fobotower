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
  /** Rendered by its own component instead of fields (e.g. the data steps). */
  custom?: "prepare";
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
/** The answer's sections and the subagents: the same settings for a skill session and for "Rules, then the model". */
const SECTIONS_FIELD: FieldSpec = { kind: "rows", path: "reasoning.sections", label: "The model answers in these sections", addLabel: "Add a section", when: (m) => get(m, "reasoning.reasoner") === "llm",
        help: "Each section is its own field: shown to the reviewer, checked, and reported on. A required section missing from an answer sends the group to a person.",
        newRow: { id: "", label: "", hint: "", required: false },
        columns: [{ key: "id", label: "Id" }, { key: "label", label: "Shown as", wide: true }, { key: "hint", label: "What it must say", kind: "textarea", wide: true }, { key: "required", label: "Required", kind: "bool" }] };
const SPECIALISTS_FIELD: FieldSpec = { kind: "rows", path: "reasoning.specialists", label: "Specialists (subagents)", addLabel: "Add a specialist", when: (m) => get(m, "reasoning.reasoner") === "llm",
        newRow: { name: "", description: "", instructions: "", tools: [] },
        columns: [{ key: "name", label: "Name" }, { key: "description", label: "When to use it", wide: true }, { key: "instructions", label: "Instructions", kind: "textarea", wide: true }, { key: "tools", label: "Tools (from the model's)", kind: "tools", within: "reasoning.tools" }] };

const hasPlaybook = (m: Json) => !!get(m, "playbook");

export const STAGES: Stage[] = [
  {
    id: "case",
    title: "What a case is",
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
      { kind: "select", path: "case.late_items", label: "When another notification arrives for a key already open", options: [
        { value: "ignore", label: "Nothing new: the existing case is the answer" },
        { value: "follow_up", label: "Open a follow-up case with only the new items" }],
        help: "e.g. MB Rec notifies late exceptions for a book and COB already being worked. A signed-off case is never changed." },
      { kind: "text", path: "case.opens_as", label: "Scheduled and event cases run as", placeholder: "aof-scheduler", help: "A service user with the roles and data scopes those cases need." },
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
    title: "Where the items come from",
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
    id: "prepare", custom: "prepare",
    title: "Prepare the data",
    says: "Generic steps, in order: prepare the data, act on the accounts (journals, posting), test controls (sampling, attestation), wait for others or child cases, read files and documents, keep clocks and parties in view. Each can run only when something holds.",
    owns: /^step_settings|is not a core step|step type/,
    fields: [],
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
    title: "Enrich each item",
    says: "Reads more data for each case (e.g. dated snapshots) and joins it onto the items.",
    owns: /^enrich|`enrich`/,
    clears: [{ path: "enrich", value: [] }],
    fields: [{ kind: "rows", path: "enrich", label: "Reads", addLabel: "Add a read", newRow: { tool: "", args: {}, keys: [], prefix: "" },
      columns: [{ key: "tool", label: "Tool", kind: "tool", access: "read" }, { key: "args", label: "Arguments", kind: "args" }, { key: "keys", label: "Join on", kind: "list" }, { key: "prefix", label: "Field prefix" }] }],
  },
  {
    id: "resolve", step: "resolve", optional: true,
    title: "Look up owners",
    says: "Looks up reference data for each item in the knowledge graph, as of the business date — e.g. which desk owned a book on the COB.",
    owns: /^resolve|knowledge\.(reference|as_of)|`resolve`/,
    clears: [{ path: "resolve", value: [] }],
    fields: [
      { kind: "text", path: "knowledge.reference", label: "Reference data", placeholder: "fobo-reference", help: "The reference file (config/agent-one-finance/knowledge/<name>.yaml)." },
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
          { key: "escalate_to", label: "Owning team" },
          { key: "any_side", label: "Settled whatever the side", kind: "bool" }] },
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
    title: "Group for one decision",
    says: "Collapses items into groups so one decision covers many — e.g. by category and side.",
    owns: /^group_by|^group_label/,
    fields: [
      { kind: "list", path: "group_by", label: "Group by", help: "Item fields; empty = one group per case." },
      { kind: "template", path: "group_label", label: "Group name", help: "e.g. {category_name} · {side_name}." },
    ],
  },
  {
    id: "agent", step: "agent",
    title: "Skill session",
    says: "One model session runs the skill: it reads what it needs with the tools listed here (through the gateway) and returns a result per item. Validate, review and record follow, as for every capability.",
    owns: /`agent`|^reasoning\.(skill_file|verdicts|escalate_verdicts|result_fields|max_turns)|`load`, `match` or `agent`/,
    fields: [
      { kind: "tools", path: "reasoning.tools", label: "Tools the model may call (read only)", access: "read" },
      { kind: "text", path: "reasoning.skill_file", label: "Skill file", help: "Under the config folder, e.g. skills/fobo.md; read in when the file is synced, so each version keeps its text." },
      { kind: "textarea", path: "reasoning.skill", label: "The skill (instructions to the model)" },
      { kind: "list", path: "reasoning.verdicts", label: "Verdicts it may give each result" },
      { kind: "list", path: "reasoning.escalate_verdicts", label: "Verdicts that go to a person as escalated" },
      { kind: "text", path: "items.id_field", label: "Each result is identified by", placeholder: "instrument" },
      { kind: "text", path: "items.amount_field", label: "Amount field" },
      { kind: "list", path: "reasoning.result_fields", label: "Fields each result carries", help: "Shown as columns; every figure in them must come from a tool result." },
      { kind: "list", path: "items.display", label: "Columns shown to reviewers" },
      { kind: "number", path: "reasoning.max_turns", label: "Turn limit for the session", min: 1, max: 200 },
      SECTIONS_FIELD,
      SPECIALISTS_FIELD,
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
      SECTIONS_FIELD,
      SPECIALISTS_FIELD,
      { kind: "number", path: "limits.max_cost_usd_per_case", label: "Model spend cap per case (USD)", min: 0, nullable: true, when: (m) => get(m, "reasoning.reasoner") === "llm" },
      { kind: "number", path: "limits.max_cost_usd_per_day", label: "Model spend cap per day (USD)", min: 0, nullable: true, when: (m) => get(m, "reasoning.reasoner") === "llm" },
    ],
  },
  {
    id: "draft", step: "draft",
    title: "Draft the summary",
    says: "Writes the case summary a reviewer reads first: what is in scope, what was proposed, what was escalated.",
    owns: /^draft/,
    fields: [{ kind: "number", path: "metrics.manual_minutes_per_item", label: "Manual minutes per item (for hours saved)", min: 1, help: "The declared basis for the efficiency figures; shown next to them." }],
  },
  {
    id: "validate", step: "validate", gate: true,
    title: "Check every figure",
    says: "Every figure the model states must trace to the case's data or a tool result; anything that does not is escalated to a person. Always on.",
    owns: /^validate/,
    fields: [],
  },
  {
    id: "review", step: "review", gate: true,
    title: "Human review",
    says: "People decide every group. The run always stops here until they do.",
    owns: /^review|^requests|^boundaries/,
    fields: [
      { kind: "list", path: "review.roles", label: "Reviewers (roles)" },
      { kind: "text", path: "review.authority_dataset", label: "Authority matrix from the bank's system (a data set)", placeholder: "authority",
        help: "A data set (rows: min_amount, max_amount, roles, approvals, lane, bulk) read by a Reference data step — the delegated-authority system stays the source. Or set tiers below." },
      { kind: "rows", path: "review.authority", label: "Authority tiers (first that holds applies)", addLabel: "Add a tier",
        help: "Who may approve a group, and how many different people must: by amount, risk band, verdict. A group above someone's authority is refused to them.",
        newRow: { when: "", label: "", roles: [], approvals: 1, lane: "standard", bulk: true },
        columns: [{ key: "label", label: "Tier" }, { key: "when", label: "When (empty = the rest)", kind: "expr" }, { key: "roles", label: "Approved by roles", kind: "list" },
          { key: "approvals", label: "People", kind: "number" }, { key: "lane", label: "Lane" }, { key: "bulk", label: "In bulk", kind: "bool" }] },
      { kind: "rows", path: "boundaries", label: "Decisions reserved for named people", addLabel: "Add a boundary",
        help: "Credit, sanctions, AML, payment release…: only these roles decide, never in bulk; the model's proposal is withheld unless allowed.",
        newRow: { when: "", verdicts: [], roles: [], model_may_propose: false, reason: "" },
        columns: [{ key: "when", label: "When", kind: "expr" }, { key: "verdicts", label: "…or verdicts", kind: "list" }, { key: "roles", label: "Decided by roles", kind: "list" },
          { key: "model_may_propose", label: "Model may propose", kind: "bool" }, { key: "reason", label: "Why" }] },
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
      { kind: "rows", path: "requests.targets", label: "Who reviewers may ask for evidence", addLabel: "Add someone to ask",
        help: "Ask rather than assume: a desk, a trader, Operations. They are notified, see only the breaks asked about, and answer in Agent One Finance.",
        newRow: { id: "", name: "", roles: [], users: [] },
        columns: [{ key: "id", label: "Id" }, { key: "name", label: "Shown as", wide: true }, { key: "roles", label: "Answered by roles", kind: "list" }, { key: "users", label: "…or people", kind: "list" }] },
      { kind: "bool", path: "requests.hold_decision", label: "A group with an open question waits for the answer" },
      { kind: "bool", path: "requests.reinvestigate_on_answer", label: "An answer sends its group back to the model" },
      { kind: "number", path: "requests.remind_after_hours", label: "Remind the people asked after (hours)", min: 0, nullable: true, when: (m) => ((get(m, "requests.targets") as unknown[]) ?? []).length > 0 },
      { kind: "number", path: "requests.escalate_after_hours", label: "Tell the reviewers a question is unanswered after (hours)", min: 0, nullable: true, when: (m) => ((get(m, "requests.targets") as unknown[]) ?? []).length > 0 },
      { kind: "bool", path: "requests.allow_attachments", label: "An answer may come with a file (kept as the case's evidence)" },
      { kind: "rows", path: "review.checklist", label: "Sign-off checklist", addLabel: "Add a question",
        help: "Questions a reviewer answers before approving a group. Required ones must be answered yes or n/a. Agent One Finance shows what it already knows next to each one.",
        newRow: { id: "", label: "", required: true, prefill: null },
        columns: [{ key: "id", label: "Id" }, { key: "label", label: "Question", wide: true }, { key: "required", label: "Required", kind: "bool" },
          { key: "prefill", label: "Agent One Finance shows", kind: "select", options: (m) => [{ value: "", label: "nothing" }, { value: "tests", label: "the tests" }, { value: "evidence", label: "evidence and answers" },
            { value: "verdict", label: "the verdict" }, { value: "category", label: "the category" },
            ...((get(m, "reasoning.sections") as { id: string; label: string }[]) ?? []).map((sec) => ({ value: sec.id, label: `section: ${sec.label}` }))] }] },
    ],
  },
  {
    id: "record", step: "record", gate: true,
    title: "Record, tickets and follow-up",
    says: "Records each decision so the next run learns from it, raises tickets for owning teams, and keeps what reviewers need next time. Always on.",
    owns: /^knowledge\.(entities|priors)|^escalation|^insights|^export|^retention|^follow_through|`escalation`/,
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
      { kind: "object", path: "follow_through", label: "Follow-through", toggle: "Re-check each decision in the next run",
        help: "An item decided last run that is gone has cleared; one still there carries carried_verdict, carried_from and carried_runs for the rules and checks (and `carried` per group).",
        empty: { series: [], order_by: "", verdicts: [] },
        fields: [
          { kind: "multi", path: "series", label: "The same series is the same", options: keyFields },
          { kind: "select", path: "order_by", label: "The next run is the next", options: keyFields },
          { kind: "list", path: "verdicts", label: "Follow these verdicts (empty = every approved group)" },
        ] },
      { kind: "object", path: "insights.unexplained", label: "Unexplained items", toggle: "List what nothing explained, for the playbook's owners",
        empty: { categories: [], lookback_days: 30 },
        fields: [
          { kind: "list", path: "categories", label: "Also count these categories as unexplained", help: "e.g. H (Novel). Items no check explained always count." },
          { kind: "number", path: "lookback_days", label: "Over the last (days)", min: 1, max: 365 },
        ] },
      { kind: "number", path: "insights.automation_after", label: "Suggest a rule after (unchanged approvals of a judgement call)", min: 2, max: 1000 },
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

/** The editor's navigation, in the order a person sets a capability up. */
export const SECTIONS: { title: string; ids: string[] }[] = [
  { title: "The case", ids: ["case", "thresholds"] },
  { title: "Data", ids: ["source", "prepare", "compare", "enrich", "resolve"] },
  { title: "Decide", ids: ["classify", "group", "agent", "reason", "draft"] },
  { title: "People and gates", ids: ["validate", "review", "record", "publish"] },
  { title: "Ownership", ids: ["owners"] },
];

/** Stages that do not apply to a skill session (the session finds the items and
 *  decides them itself), and the session's own stage, which only a skill session shows. */
const NOT_IN_SESSION = new Set(["source", "compare", "enrich", "resolve", "classify", "group", "reason"]);

export function stagesFor(stages: Stage[], m: Json): Stage[] {
  const session = ((get(m, "steps") as string[]) ?? []).includes("agent");
  return stages.filter((s) => (session ? !NOT_IN_SESSION.has(s.id) : s.id !== "agent"));
}

/** Steps in the engine's order (load and match are the item source). */
export const STEP_ORDER = ["load", "match", "agent", "enrich", "resolve", "classify", "compare", "group", "reason", "draft", "validate", "review", "record", "publish"];

/** The stage a server problem belongs to (the first that owns it). */
export function stageOf(problem: string): string {
  const gate = /^tollgates\.([a-z]+):/.exec(problem);
  if (gate) return STAGES.find((s) => s.step === gate[1])?.id ?? "pipeline";
  if (/required|gates must|must be the last|must pause|must come right after|needs .* produced by no earlier|listed twice|unknown step|cannot stop before/.test(problem)) return "pipeline";
  return STAGES.find((s) => s.owns.test(problem))?.id ?? "pipeline";
}
