// "Prepare the data": the capability's configurable steps (steps v2) — add one
// of the generic types, set it up with a form, run it only `when` something
// holds, put it in order, remove it. Each is checked by the server like any
// other setting; team groups may change the settings their capability allows.

import { useState } from "react";
import { ArrowDown, ArrowUp, Plus, Trash2 } from "lucide-react";

import { Field, type Ctx, type FieldSpec } from "./fields";
import { get, setPath, type Json } from "./paths";

export const DATA_TYPES: { type: string; label: string; says: string; empty: Json }[] = [
  { type: "dataset", label: "Reference data", says: "Reads a named data set beside the items: FX rates, a budget, limits, prior periods.", empty: { name: "", tool: "", args: {} } },
  { type: "derive", label: "Computed fields", says: "Adds fields computed from each item, the case and policy (age, ratios, flags).", empty: { fields: {} } },
  { type: "filter", label: "Filter", says: "Keeps the items that match; the others stay on the case, marked with the reason.", empty: { keep_when: "", reason: "filtered out" } },
  { type: "convert", label: "Currency conversion", says: "Converts amounts to one currency with the case's own rates; a missing rate is flagged, never assumed.", empty: { amounts: [], currency_field: "currency", to: "GBP", rates: "" } },
  { type: "bucket", label: "Bands", says: "Puts each item in a band of a field: ageing, size, service level.", empty: { field: "", as: "", bands: [{ label: "", upto: null }] } },
  { type: "dedupe", label: "Duplicates", says: "Finds items with the same key fields; duplicates are set aside (kept on the case) or marked.", empty: { keys: [], drop: true } },
  { type: "aggregate", label: "Roll up", says: "Rolls items up by key fields with totals and counts — into the items or into a data set.", empty: { by: [], sum: [], into: "items" } },
  { type: "transform", label: "Team logic (tool)", says: "Sends the items to the team's own tool and uses what it returns — for logic expressions cannot hold.", empty: { tool: "", args: {}, send: [], returns: "fields" } },
];
const TYPE = Object.fromEntries(DATA_TYPES.map((t) => [t.type, t]));

const settings = (m: Json) => (get(m, "step_settings") as Record<string, Json>) ?? {};
const typeOf = (m: Json, id: string) => (settings(m)[id]?.type as string | undefined) ?? id;
/** Ids of the configurable steps, in run order. */
export const dataSteps = (m: Json) => ((get(m, "steps") as string[]) ?? []).filter((id) => TYPE[typeOf(m, id)]);
const datasetNames = (m: Json) => dataSteps(m).filter((id) => typeOf(m, id) === "dataset")
  .map((id) => get(m, `step_settings.${id}.with.name`) as string).filter(Boolean).map((v) => ({ value: v }));

function fields(id: string, type: string): FieldSpec[] {
  const w = `step_settings.${id}.with`;
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
    default: return [];
  }
}

/** Where a new step goes: after the last configurable step, else right after the item source. */
function insertAt(steps: string[], m: Json): number {
  const last = dataSteps(m).at(-1);
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
    const at = insertAt(all, w);
    const out = setPath(w, "steps", [...all.slice(0, at), id, ...all.slice(at)]);
    return setPath(out, `step_settings.${id}`, { type: adding, label: TYPE[adding].label, with: TYPE[adding].empty });
  });
  const remove = (id: string) => setWorking((w) => {
    const rest = { ...settings(w) };
    delete rest[id];
    return setPath(setPath(w, "steps", ((get(w, "steps") as string[]) ?? []).filter((s) => s !== id)), "step_settings", rest);
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
      {ids.length === 0 && <p className="text-sm text-surface-500">No data steps yet. Add one to read reference data, compute fields, filter, convert, band, deduplicate, roll up or call your team's own tool.</p>}
      {ids.map((id) => {
        const t = TYPE[typeOf(m, id)];
        return (
          <section key={id} aria-label={`Step ${id}`} className="rounded-lg border border-surface-200 p-3">
            <div className="flex flex-wrap items-center gap-2">
              <span className="rounded bg-primary-50 px-1.5 py-0.5 text-[11px] font-medium text-primary-800">{t.label}</span>
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
              {fields(id, t.type).map((f) => <Field key={f.path} ctx={ctx} spec={f} />)}
            </div>
          </section>
        );
      })}
      {!stepsLocked && (
        <div className="flex flex-wrap items-end gap-2">
          <label className="text-xs font-medium text-surface-600">Add a step
            <select aria-label="Step type to add" value={adding} onChange={(e) => setAdding(e.target.value)} className="mt-1 block rounded-lg border border-surface-300 bg-card px-2 py-1.5 text-sm">
              {DATA_TYPES.map((t) => <option key={t.type} value={t.type}>{t.label}</option>)}
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
