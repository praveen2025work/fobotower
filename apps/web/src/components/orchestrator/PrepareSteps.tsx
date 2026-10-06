// "Prepare the data": the capability's configurable steps (steps v2) — add one
// of the generic types, set it up with a form, run it only `when` something
// holds, put it in order, remove it. Each is checked by the server like any
// other setting; team groups may change the settings their capability allows.

import { useState } from "react";
import { ArrowDown, ArrowUp, Plus, Trash2 } from "lucide-react";

import { Field, type Ctx, type FieldSpec } from "./fields";
import { get, setPath, type Json } from "./paths";

type Place = "items" | "groups" | "after_record";
export interface StepTypeInfo { type: string; label: string; family: string; says: string; empty: Json; place?: Place; person?: boolean }

export const DATA_TYPES: StepTypeInfo[] = [
  // data
  { type: "dataset", family: "Data", label: "Reference data", says: "Reads a named data set beside the items: FX rates, a budget, limits, prior periods.", empty: { name: "", tool: "", args: {} } },
  { type: "derive", family: "Data", label: "Computed fields", says: "Adds fields computed from each item, the case and policy (age, ratios, flags).", empty: { fields: {} } },
  { type: "filter", family: "Data", label: "Filter", says: "Keeps the items that match; the others stay on the case, marked with the reason.", empty: { keep_when: "", reason: "filtered out" } },
  { type: "convert", family: "Data", label: "Currency conversion", says: "Converts amounts to one currency with the case's own rates; a missing rate is flagged, never assumed.", empty: { amounts: [], currency_field: "currency", to: "GBP", rates: "" } },
  { type: "bucket", family: "Data", label: "Bands", says: "Puts each item in a band of a field: ageing, size, service level.", empty: { field: "", as: "", bands: [{ label: "", upto: null }] } },
  { type: "dedupe", family: "Data", label: "Duplicates", says: "Finds items with the same key fields; duplicates are set aside (kept on the case) or marked.", empty: { keys: [], drop: true } },
  { type: "aggregate", family: "Data", label: "Roll up", says: "Rolls items up by key fields with totals and counts — into the items or into a data set.", empty: { by: [], sum: [], into: "items" } },
  { type: "transform", family: "Data", label: "Team logic (tool)", says: "Sends the items to the team's own tool and uses what it returns — for logic expressions cannot hold.", empty: { tool: "", args: {}, send: [], returns: "fields" } },
  // accounting actions
  { type: "recompute", family: "Accounting", label: "Recompute and compare", says: "Recalculates a figure (fees, interest, accruals) by formula or the team's tool and compares it with what was booked.", empty: { formula: "", compare_to: "", as: "recomputed", tolerance: 0.01 } },
  { type: "schedule", family: "Accounting", label: "Schedule over periods", says: "Spreads each item's amount over periods (prepayments, accrual release) into a data set.", empty: { amount: "amount", periods: 12, start: "$case.period", into: "schedule" } },
  { type: "period_check", family: "Accounting", label: "Period open?", says: "Stops the run, to a person, if the accounting period is closed for the entity.", empty: { tool: "", args: {}, status_field: "status", open_values: ["open"] } },
  { type: "propose_entries", family: "Accounting", label: "Journal entries", says: "Drafts balanced journals for the groups that need them; an unbalanced entry or unknown account is caught first.", place: "groups",
    empty: { when: "status == 'proposed'", period: "$case.period", chart: null, lines: [{ account: "{account}", side: "debit", amount: "abs(total)", narrative: "{label}" }, { account: "", side: "credit", amount: "abs(total)", narrative: "{label}" }] } },
  { type: "post", family: "Accounting", label: "Post journals", says: "Posts the approved journals to the ledger after a second person releases them — the ledger's own check first; each journal once.", place: "after_record", person: true,
    empty: { tool: "", dry_run_tool: null, args: {}, approver_roles: [] } },
  // assurance
  { type: "flux", family: "Assurance", label: "Change over periods", says: "Compares each item with its own history: change, % change and how unusual.", empty: { history: "", key: "", value: "amount", history_value: "value", prefix: "flux" } },
  { type: "anomaly", family: "Assurance", label: "Unusual against history", says: "Flags items far from their own history (a z-score threshold) — statistics, no model.", empty: { history: "", key: "", value: "amount", history_value: "value", threshold: 3 } },
  { type: "consistency", family: "Assurance", label: "Consistency checks", says: "Checks totals across data sets (sub-ledger = GL); each failing check becomes an item to investigate.",
    empty: { checks: [{ id: "", left: { source: "items", field: "amount" }, right: { source: "", field: "" }, tolerance: 0.01, message: "" }] } },
  { type: "sample", family: "Assurance", label: "Sample", says: "A reproducible sample (random, largest or by value; stratified); the rest stay on the case, marked.", empty: { method: "random", size: 25, field: null, stratify_by: null, always_include_when: null } },
  { type: "score", family: "Assurance", label: "Risk score", says: "A weighted score from named factors, with its reasons and a band review lanes can use.", empty: { factors: [{ when: "", weight: 10, label: "" }], as: "score", bands: [] } },
  { type: "attest", family: "Assurance", label: "Owner attestation", says: "An owner certifies a statement at a tollgate; recorded with who, when, evidence and expiry.", place: "groups", person: true,
    empty: { statement: "", roles: [], evidence_required: false, valid_for_days: null } },
  // orchestration
  { type: "await", family: "Orchestration", label: "Wait for an event", says: "The run waits for an event (a reply, a confirmation) or for its child cases, with a timeout.", empty: { event: "", timeout_hours: 24, on_timeout: "escalate", roles: [] } },
  { type: "spawn", family: "Orchestration", label: "Child cases", says: "Opens a child case per item in another capability; a later wait for `children` rolls them up.", empty: { capability: "", key: {}, max_children: 200 } },
  { type: "compose", family: "Orchestration", label: "Draft a message", says: "Drafts each group's outbound message for the reviewer; sent only by an approved outreach step.", place: "groups",
    empty: { when: "status == 'proposed'", to: "", subject: "", body: "" } },
  { type: "report", family: "Orchestration", label: "Report", says: "Writes the case's report (configuration, findings, decisions, data used) as a PDF kept with the case.", place: "after_record", empty: { name: "case-report" } },
  // acquisition
  { type: "match_n", family: "Acquisition", label: "Match several systems", says: "Matches two or more systems by key (order, receipt, invoice) with many-to-one sums; keeps what does not agree.",
    empty: { keys: [], tolerance: 0.01, many_to_one: true, sources: [{ label: "", tool: "", args: {}, amount_field: "amount" }, { label: "", tool: "", args: {}, amount_field: "amount" }] } },
  { type: "intake", family: "Acquisition", label: "File intake", says: "Reads a workbook into items with a column map and checks; rows that fail are kept aside, with why.", empty: { tool: "", args: {}, columns: {}, required: [], numbers: [], id_field: "" } },
  { type: "extract", family: "Acquisition", label: "Read a document", says: "Reads fields from a document (patterns first, then the model); values must appear in it; uncertain or regulated ones go to a person.",
    empty: { tool: "", args: {}, fields: [{ name: "", hint: "", required: false, pattern: null }], accept_confidence: 0.9, regulated: false } },
  // time, context and parties
  { type: "clock", family: "Time and parties", label: "Clocks", says: "Service-level or regulatory clocks per item (hours or business days); people are warned before and told on breach.",
    empty: { clocks: [{ id: "", label: "", starts: "case_opened", hours: 24, business_days: null, warn_before_hours: 4 }] } },
  { type: "timeline", family: "Time and parties", label: "Timeline", says: "One ordered timeline of events from several systems, for the reviewer and the model.", empty: { sources: [{ tool: "", args: {}, time_field: "", label: "" }], into: "timeline", for_model: true } },
  { type: "link", family: "Time and parties", label: "Related cases", says: "Earlier cases about the same client, account or counterparty, and how they ended.", empty: { match_on: [], lookback_days: 365, capabilities: [], limit: 5 } },
  { type: "screen", family: "Time and parties", label: "Name screening (candidates)", says: "Fuzzy-matches names against a list and marks candidates for a person; never clears or confirms a match.", empty: { list: "", fields: [], list_field: "name", threshold: 0.85 } },
  { type: "outreach", family: "Time and parties", label: "Send to the other party", says: "Sends each drafted message through the bank's channel, after a person approves sending at the tollgate before it.", place: "groups", person: true,
    empty: { tool: "", roles: [], when: "status == 'proposed'" } },
];
const TYPE = Object.fromEntries(DATA_TYPES.map((t) => [t.type, t]));
const FAMILIES = [...new Set(DATA_TYPES.map((t) => t.family))];

const settings = (m: Json) => (get(m, "step_settings") as Record<string, Json>) ?? {};
const typeOf = (m: Json, id: string) => (settings(m)[id]?.type as string | undefined) ?? id;
/** Ids of the configurable steps, in run order. */
export const dataSteps = (m: Json) => ((get(m, "steps") as string[]) ?? []).filter((id) => TYPE[typeOf(m, id)]);
const datasetNames = (m: Json) => dataSteps(m).flatMap((id) => {
  const w = `step_settings.${id}.with`;
  const t = typeOf(m, id);
  const n = t === "dataset" ? get(m, `${w}.name`) : ["schedule", "timeline"].includes(t) ? (get(m, `${w}.into`) ?? t) : null;
  return n ? [{ value: n as string }] : [];
});

function fields(id: string, type: string): FieldSpec[] {
  const w = `step_settings.${id}.with`;
  const args: FieldSpec = { kind: "kv", path: `${w}.args`, label: "Arguments", keyLabel: "Argument", valueLabel: "Value ($case.<field>)" };
  const history: FieldSpec[] = [
    { kind: "select", path: `${w}.history`, label: "History (a data set)", options: datasetNames },
    { kind: "text", path: `${w}.key`, label: "Matched on the field", placeholder: "account" },
    { kind: "text", path: `${w}.value`, label: "The item's figure" },
    { kind: "text", path: `${w}.history_value`, label: "The history's figure" }];
  switch (type) {
    case "dataset": return [
      { kind: "text", path: `${w}.name`, label: "Name it", placeholder: "fx", help: "Other steps refer to it by this name." },
      { kind: "tool", path: `${w}.tool`, label: "Read with", access: "read" },
      { kind: "kv", path: `${w}.args`, label: "Arguments", keyLabel: "Argument", valueLabel: "Value ($case.<field>)" }];
    case "derive": return [
      { kind: "kv", path: `${w}.fields`, label: "Fields", keyLabel: "New field", valueLabel: "Expression, e.g. hours_between(received_at, case.date)" }];
    case "filter": return [
      { kind: "expr", path: `${w}.keep_when`, label: "Keep items when", placeholder: "not is_test" },
      { kind: "text", path: `${w}.reason`, label: "Reason shown on the others" }];
    case "convert": return [
      { kind: "list", path: `${w}.amounts`, label: "Amount fields" },
      { kind: "text", path: `${w}.currency_field`, label: "Currency field" },
      { kind: "text", path: `${w}.to`, label: "Convert to", placeholder: "GBP" },
      { kind: "select", path: `${w}.rates`, label: "Rates (a data set)", options: datasetNames }];
    case "bucket": return [
      { kind: "text", path: `${w}.field`, label: "Band this field" },
      { kind: "text", path: `${w}.as`, label: "Into the field" },
      { kind: "rows", path: `${w}.bands`, label: "Bands, in order", addLabel: "Add a band", newRow: { label: "", upto: null },
        columns: [{ key: "label", label: "Label", wide: true }, { key: "upto", label: "Up to (empty = the rest)", kind: "number" }] }];
    case "dedupe": return [
      { kind: "list", path: `${w}.keys`, label: "Same when these fields match" },
      { kind: "bool", path: `${w}.drop`, label: "Set duplicates aside (kept on the case)" }];
    case "aggregate": return [
      { kind: "list", path: `${w}.by`, label: "Roll up by" },
      { kind: "list", path: `${w}.sum`, label: "Total these fields" },
      { kind: "text", path: `${w}.into`, label: "Into", help: "items, or a data set name" }];
    case "transform": return [
      { kind: "tool", path: `${w}.tool`, label: "The team's tool", access: "read" },
      { kind: "kv", path: `${w}.args`, label: "Arguments", keyLabel: "Argument", valueLabel: "Value ($case.<field>)" },
      { kind: "list", path: `${w}.send`, label: "Fields sent (empty = all)", help: "Send only what the tool needs." },
      { kind: "select", path: `${w}.returns`, label: "It returns", options: [{ value: "fields", label: "fields to add to the items" }, { value: "items", label: "the items themselves" }] }];
    case "recompute": return [
      { kind: "expr", path: `${w}.formula`, label: "Formula", placeholder: "round(balance * rate / 365, 2)", help: "Or leave empty and name the team's tool." },
      { kind: "tool", path: `${w}.tool`, label: "…or the team's tool", access: "read" },
      { kind: "text", path: `${w}.compare_to`, label: "Compare with the booked field" },
      { kind: "text", path: `${w}.as`, label: "Into the field" },
      { kind: "number", path: `${w}.tolerance`, label: "Tolerance", min: 0, step: 0.01 }];
    case "schedule": return [
      { kind: "text", path: `${w}.amount`, label: "Amount field" },
      { kind: "number", path: `${w}.periods`, label: "Periods", min: 1, max: 600 },
      { kind: "text", path: `${w}.start`, label: "First period", placeholder: "$case.period or an item field" },
      { kind: "text", path: `${w}.into`, label: "Into the data set" }];
    case "period_check": return [
      { kind: "tool", path: `${w}.tool`, label: "Period status from", access: "read" }, args,
      { kind: "list", path: `${w}.open_values`, label: "Open when the status is" }];
    case "propose_entries": return [
      { kind: "expr", path: `${w}.when`, label: "For groups where" },
      { kind: "text", path: `${w}.period`, label: "Accounting period", placeholder: "$case.period" },
      { kind: "select", path: `${w}.chart`, label: "Chart of accounts (a data set)", options: datasetNames, nullable: true },
      { kind: "rows", path: `${w}.lines`, label: "Journal lines (debits must equal credits)", addLabel: "Add a line",
        newRow: { account: "", side: "debit", amount: "abs(total)", narrative: "{label}" },
        columns: [{ key: "account", label: "Account ({field} allowed)" }, { key: "side", label: "Side", kind: "select", options: [{ value: "debit" }, { value: "credit" }] },
          { key: "amount", label: "Amount (expression)", wide: true }, { key: "narrative", label: "Narrative", wide: true }] }];
    case "post": return [
      { kind: "tool", path: `${w}.tool`, label: "Ledger write tool", access: "write" },
      { kind: "tool", path: `${w}.dry_run_tool`, label: "Ledger check (called first)", access: "read" }, args,
      { kind: "list", path: `${w}.approver_roles`, label: "Released by (roles; never a reviewer of the case)" }];
    case "flux": return [...history, { kind: "text", path: `${w}.prefix`, label: "Field prefix" }];
    case "anomaly": return [...history, { kind: "number", path: `${w}.threshold`, label: "Unusual from (z-score)", min: 0.5, step: 0.5 }];
    case "consistency": return [
      { kind: "rows", path: `${w}.checks`, label: "Checks", addLabel: "Add a check",
        newRow: { id: "", left: { source: "items", field: "amount" }, right: { source: "", field: "" }, tolerance: 0.01, message: "" },
        columns: [{ key: "id", label: "Id" }, { key: "left.source", label: "Left: items or data set" }, { key: "left.field", label: "Left field" },
          { key: "right.source", label: "Right: data set" }, { key: "right.field", label: "Right field" },
          { key: "tolerance", label: "Tolerance", kind: "number" }, { key: "message", label: "Message", wide: true }] }];
    case "sample": return [
      { kind: "select", path: `${w}.method`, label: "Method", options: [{ value: "random", label: "random" }, { value: "top", label: "largest first" }, { value: "monetary", label: "by value (monetary unit)" }] },
      { kind: "number", path: `${w}.size`, label: "Size", min: 1, nullable: true },
      { kind: "number", path: `${w}.percent`, label: "…or percent", min: 0, max: 100, nullable: true },
      { kind: "text", path: `${w}.field`, label: "Value field (largest / by value)" },
      { kind: "text", path: `${w}.stratify_by`, label: "Stratify by (optional)" },
      { kind: "expr", path: `${w}.always_include_when`, label: "Always include when (optional)" }];
    case "score": return [
      { kind: "rows", path: `${w}.factors`, label: "Factors", addLabel: "Add a factor", newRow: { when: "", weight: 10, label: "" },
        columns: [{ key: "label", label: "Factor" }, { key: "when", label: "When", wide: true }, { key: "weight", label: "Weight", kind: "number" }] },
      { kind: "text", path: `${w}.as`, label: "Into the field" },
      { kind: "rows", path: `${w}.bands`, label: "Bands, in order", addLabel: "Add a band", newRow: { label: "", upto: null },
        columns: [{ key: "label", label: "Band", wide: true }, { key: "upto", label: "Up to (empty = the rest)", kind: "number" }] }];
    case "attest": return [
      { kind: "textarea", path: `${w}.statement`, label: "Statement the owner certifies" },
      { kind: "list", path: `${w}.roles`, label: "Attested by (roles)" },
      { kind: "bool", path: `${w}.evidence_required`, label: "Evidence must be on the case first" },
      { kind: "number", path: `${w}.valid_for_days`, label: "Valid for (days)", min: 1, nullable: true }];
    case "await": return [
      { kind: "text", path: `${w}.event`, label: "Event", placeholder: "bank_confirmation, or children", help: "`children`: the child cases a `Child cases` step opened, all finished." },
      { kind: "number", path: `${w}.timeout_hours`, label: "Timeout (hours)", min: 0, nullable: true },
      { kind: "select", path: `${w}.on_timeout`, label: "On timeout", options: [{ value: "escalate", label: "escalate to a person" }, { value: "continue", label: "carry on" }] },
      { kind: "list", path: `${w}.roles`, label: "May deliver it by hand (roles)" }];
    case "spawn": return [
      { kind: "text", path: `${w}.capability`, label: "Child capability" },
      { kind: "kv", path: `${w}.key`, label: "Child case key", keyLabel: "Key field", valueLabel: "$item.<field>, $case.<field> or a value" },
      { kind: "number", path: `${w}.max_children`, label: "At most", min: 1, max: 2000 }];
    case "compose": return [
      { kind: "expr", path: `${w}.when`, label: "For groups where" },
      { kind: "template", path: `${w}.to`, label: "To" },
      { kind: "template", path: `${w}.subject`, label: "Subject" },
      { kind: "textarea", path: `${w}.body`, label: "Body ({field}, {total}, {count}, {comment})" }];
    case "report": return [{ kind: "text", path: `${w}.name`, label: "Report name" }];
    case "match_n": return [
      { kind: "list", path: `${w}.keys`, label: "Matched on" },
      { kind: "number", path: `${w}.tolerance`, label: "Tolerance", min: 0, step: 0.01 },
      { kind: "bool", path: `${w}.many_to_one`, label: "Sum each system's rows per key first" },
      { kind: "rows", path: `${w}.sources`, label: "Systems (two to six)", addLabel: "Add a system",
        newRow: { label: "", tool: "", args: {}, amount_field: "amount" },
        columns: [{ key: "label", label: "Short name" }, { key: "tool", label: "Read with", kind: "tool", access: "read" }, { key: "amount_field", label: "Amount field" }] }];
    case "intake": return [
      { kind: "tool", path: `${w}.tool`, label: "Read the file with", access: "read" }, args,
      { kind: "kv", path: `${w}.columns`, label: "Columns", keyLabel: "Item field", valueLabel: "Column in the file" },
      { kind: "text", path: `${w}.id_field`, label: "Item id field" },
      { kind: "list", path: `${w}.required`, label: "Required fields" },
      { kind: "list", path: `${w}.numbers`, label: "Number fields" }];
    case "extract": return [
      { kind: "tool", path: `${w}.tool`, label: "Read the document with", access: "read" }, args,
      { kind: "rows", path: `${w}.fields`, label: "Fields to read", addLabel: "Add a field", newRow: { name: "", hint: "", required: false, pattern: null },
        columns: [{ key: "name", label: "Field" }, { key: "hint", label: "As written in the document", wide: true },
          { key: "pattern", label: "Pattern (optional)" }, { key: "required", label: "Required", kind: "bool" }] },
      { kind: "number", path: `${w}.accept_confidence`, label: "A person checks values below (confidence)", min: 0, max: 1, step: 0.05 },
      { kind: "bool", path: `${w}.regulated`, label: "Regulated: a person checks every value" }];
    case "clock": return [
      { kind: "rows", path: `${w}.clocks`, label: "Clocks", addLabel: "Add a clock",
        newRow: { id: "", label: "", starts: "case_opened", hours: 24, business_days: null, warn_before_hours: 4 },
        columns: [{ key: "id", label: "Id" }, { key: "label", label: "Shown as", wide: true }, { key: "starts", label: "Starts (field or case_opened)" },
          { key: "hours", label: "Hours", kind: "number" }, { key: "business_days", label: "…or business days", kind: "number" },
          { key: "warn_before_hours", label: "Warn before (h)", kind: "number" }, { key: "pause_hours_field", label: "Paused hours field" }] }];
    case "timeline": return [
      { kind: "rows", path: `${w}.sources`, label: "Sources", addLabel: "Add a source", newRow: { tool: "", args: {}, time_field: "", label: "" },
        columns: [{ key: "label", label: "Shown as" }, { key: "tool", label: "Read with", kind: "tool", access: "read" }, { key: "time_field", label: "Time field" }] },
      { kind: "text", path: `${w}.into`, label: "Into the data set" },
      { kind: "bool", path: `${w}.for_model`, label: "The model reads it when it investigates" }];
    case "link": return [
      { kind: "list", path: `${w}.match_on`, label: "Same when these fields match", placeholder: "client, account" },
      { kind: "number", path: `${w}.lookback_days`, label: "Look back (days)", min: 1, max: 3650 },
      { kind: "list", path: `${w}.capabilities`, label: "In capabilities (empty = all)" },
      { kind: "number", path: `${w}.limit`, label: "At most", min: 1, max: 50 }];
    case "screen": return [
      { kind: "select", path: `${w}.list`, label: "List (a data set)", options: datasetNames },
      { kind: "list", path: `${w}.fields`, label: "Names in these fields" },
      { kind: "text", path: `${w}.list_field`, label: "Name field in the list" },
      { kind: "number", path: `${w}.threshold`, label: "Candidate from (similarity)", min: 0.5, max: 1, step: 0.05 }];
    case "outreach": return [
      { kind: "tool", path: `${w}.tool`, label: "The bank's channel", access: "write" },
      { kind: "list", path: `${w}.roles`, label: "Sending approved by (roles)" },
      { kind: "expr", path: `${w}.when`, label: "For groups where" }];
    default: return [];
  }
}

/** Where a new step goes: item steps after the last item step (else after the
 * item source); group steps after `reason`; write-back and reports after `record`. */
function insertAt(steps: string[], m: Json, place: Place = "items"): number {
  if (place === "after_record") return steps.length;
  if (place === "groups") {
    const after = [...steps].reverse().find((s) => s === "reason" || TYPE[typeOf(m, s)]?.place === "groups");
    return after ? steps.indexOf(after) + 1 : steps.length;
  }
  const last = dataSteps(m).filter((s) => !TYPE[typeOf(m, s)].place).at(-1);
  if (last) return steps.indexOf(last) + 1;
  const src = steps.findIndex((s) => s === "load" || s === "match");
  return src < 0 ? 0 : src + 1;
}

export default function PrepareSteps({ ctx, setWorking, stepsLocked }: {
  ctx: Ctx; setWorking: (f: (m: Json) => Json) => void; stepsLocked: string | null;
}) {
  const [adding, setAdding] = useState("derive");
  const m = ctx.m;
  const ids = dataSteps(m);
  const steps = (get(m, "steps") as string[]) ?? [];

  const add = () => setWorking((w) => {
    const all = (get(w, "steps") as string[]) ?? [];
    let n = 1;
    while (all.includes(`${adding}_${n}`)) n += 1;
    const id = `${adding}_${n}`;
    const t = TYPE[adding];
    const at = insertAt(all, w, t.place);
    let out = setPath(w, "steps", [...all.slice(0, at), id, ...all.slice(at)]);
    // a person approves first: attestation, sending, posting
    if (t.person) out = setPath(out, "pause_before", [...((get(out, "pause_before") as string[]) ?? []), id]);
    return setPath(out, `step_settings.${id}`, { type: adding, label: t.label, with: t.empty });
  });
  const remove = (id: string) => setWorking((w) => {
    const rest = { ...settings(w) };
    delete rest[id];
    const out = setPath(setPath(w, "steps", ((get(w, "steps") as string[]) ?? []).filter((s) => s !== id)), "step_settings", rest);
    return setPath(out, "pause_before", ((get(out, "pause_before") as string[]) ?? []).filter((s) => s !== id));
  });
  const move = (id: string, by: -1 | 1) => setWorking((w) => {
    const all = [...((get(w, "steps") as string[]) ?? [])];
    const i = all.indexOf(id);
    const j = i + by;
    if (j < 0 || j >= all.length || ["validate", "review", "record", "publish"].includes(all[j])) return w;
    [all[i], all[j]] = [all[j], all[i]];
    return setPath(w, "steps", all);
  });

  return (
    <div className="mt-4 space-y-3">
      {ids.length === 0 && <p className="text-sm text-surface-500">No configurable steps yet. Add one to prepare the data, act on the accounts, test controls, wait for others, read files and documents, or keep clocks and parties in view.</p>}
      {ids.map((id) => {
        const t = TYPE[typeOf(m, id)];
        return (
          <section key={id} aria-label={`Step ${id}`} className="rounded-lg border border-surface-200 p-3">
            <div className="flex flex-wrap items-center gap-2">
              <span className="rounded bg-primary-50 px-1.5 py-0.5 text-[11px] font-medium text-primary-800">{t.label}</span>
              <span className="text-[11px] text-surface-400">{t.family}</span>
              {t.person && <span className="rounded bg-amber-50 px-1.5 py-0.5 text-[11px] text-amber-800">a person approves first</span>}
              <code className="text-[11px] text-surface-500">{id}</code>
              <span className="text-[11px] text-surface-400">step {steps.indexOf(id) + 1} of {steps.length}</span>
              {!stepsLocked && (
                <span className="ml-auto flex gap-1">
                  <button type="button" aria-label={`Move ${id} earlier`} onClick={() => move(id, -1)} className="rounded p-1 text-surface-500 hover:bg-surface-100"><ArrowUp size={13} /></button>
                  <button type="button" aria-label={`Move ${id} later`} onClick={() => move(id, 1)} className="rounded p-1 text-surface-500 hover:bg-surface-100"><ArrowDown size={13} /></button>
                  <button type="button" aria-label={`Remove ${id}`} onClick={() => remove(id)} className="rounded p-1 text-red-600 hover:bg-red-50"><Trash2 size={13} /></button>
                </span>
              )}
            </div>
            <p className="mt-1 text-xs text-surface-500">{t.says}</p>
            <div className="mt-3 grid gap-3 sm:grid-cols-2">
              <Field ctx={ctx} spec={{ kind: "text", path: `step_settings.${id}.label`, label: "Called" }} />
              <Field ctx={ctx} spec={{ kind: "expr", path: `step_settings.${id}.when`, label: "Run only when (optional)", placeholder: "case.entity == 'US01'" }} />
              {fields(id, t.type).map((f) => (
                <div key={f.path} className={["rows", "textarea", "kv"].includes(f.kind) ? "sm:col-span-2" : undefined}>
                  <Field ctx={ctx} spec={f} />
                </div>
              ))}
            </div>
          </section>
        );
      })}
      {!stepsLocked && (
        <div className="flex flex-wrap items-end gap-2">
          <label className="text-xs font-medium text-surface-600">Add a step
            <select aria-label="Step type to add" value={adding} onChange={(e) => setAdding(e.target.value)} className="mt-1 block rounded-lg border border-surface-300 bg-card px-2 py-1.5 text-sm">
              {FAMILIES.map((f) => (
                <optgroup key={f} label={f}>
                  {DATA_TYPES.filter((t) => t.family === f).map((t) => <option key={t.type} value={t.type}>{t.label}</option>)}
                </optgroup>
              ))}
            </select>
          </label>
          <button type="button" onClick={add} className="inline-flex items-center gap-1 rounded-lg border border-primary-300 px-3 py-1.5 text-xs font-medium text-primary-700 hover:bg-primary-50">
            <Plus size={12} /> Add
          </button>
        </div>
      )}
      {stepsLocked && <p className="text-[11px] text-surface-500">Which steps run is {stepsLocked === "set by the capability" ? "set by the capability" : "for its owners to change"}; settings it allows are editable here.</p>}
    </div>
  );
}
