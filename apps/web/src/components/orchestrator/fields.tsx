// Reusable form controls for configuration, driven by a field description
// (stages.ts). Each control reads and writes one dotted path of the working
// manifest; a control the owner may not change is shown, locked, with why.

import { useEffect, useState } from "react";
import clsx from "clsx";
import { Lock, Plus, Trash2 } from "lucide-react";

import { get, type Json } from "./paths";

export type Opt = { value: string; label?: string };
type Opts = Opt[] | ((m: Json) => Opt[]);

/** One column of a table (rows, dict). */
export interface Column {
  key: string;                // dotted inside the row, e.g. "then.status"
  label: string;
  kind?: "text" | "expr" | "select" | "bool" | "list" | "tool" | "tools" | "number" | "textarea" | "args";
  options?: Opts;
  access?: "read" | "write";  // for tools
  within?: string;            // for tools: only those listed at this path of the manifest
  wide?: boolean;
}

interface Base {
  path: string;
  label: string;
  help?: string;
  when?: (m: Json) => boolean;          // shown only when this holds
}
export type FieldSpec =
  | (Base & { kind: "text" | "template" | "expr" | "textarea" | "cron" | "time"; placeholder?: string })
  | (Base & { kind: "number"; min?: number; max?: number; step?: number; nullable?: boolean })
  | (Base & { kind: "bool" })
  | (Base & { kind: "select"; options: Opts; nullable?: boolean })
  | (Base & { kind: "multi"; options: Opts })
  | (Base & { kind: "list"; placeholder?: string })
  | (Base & { kind: "tool" | "tools"; access: "read" | "write" })
  | (Base & { kind: "kv"; keyLabel: string; valueLabel: string })
  | (Base & { kind: "rows"; columns: Column[] | ((m: Json) => Column[]); newRow: Json; addLabel: string })
  | (Base & { kind: "dict"; columns: Column[]; keyLabel: string; newEntry: Json; addLabel: string })
  | (Base & { kind: "matrix"; rows: string; cols: string; options: Opts })
  | (Base & { kind: "policy" })
  | (Base & { kind: "object"; fields: FieldSpec[]; toggle: string; empty: Json });

export interface Ctx {
  m: Json;
  tools: { name: string; description: string; access: "read" | "write" }[];
  locked: (path: string) => string | null;   // why a path cannot be changed, or null
  set: (path: string, value: unknown) => void;
}

const input = "block w-full rounded-lg border border-surface-300 bg-card px-2 py-1.5 text-sm text-surface-800 disabled:bg-surface-100 disabled:text-surface-500";
const mono = "font-mono text-xs";

const opts = (o: Opts, m: Json) => (typeof o === "function" ? o(m) : o);

/** A comma-separated list that keeps what the user is typing until they leave the box. */
function ListInput({ value, onChange, disabled, placeholder, id }: { value: string[]; onChange: (v: string[]) => void; disabled: boolean; placeholder?: string; id?: string }) {
  const [text, setText] = useState(value.join(", "));
  useEffect(() => setText(value.join(", ")), [value.join("|")]); // eslint-disable-line react-hooks/exhaustive-deps
  return (
    <input
      id={id}
      value={text}
      disabled={disabled}
      placeholder={placeholder ?? "comma-separated"}
      onChange={(e) => setText(e.target.value)}
      onBlur={() => onChange(text.split(",").map((s) => s.trim()).filter(Boolean))}
      className={input}
    />
  );
}

/** Tool arguments as one line, "book=$case.book, cob=$case.cob", kept as typed until the box is left. */
function ArgsInput({ value, onChange, disabled }: { value: Json; onChange: (v: Json) => void; disabled: boolean }) {
  const show = (v: Json) => Object.entries(v ?? {}).map(([k, x]) => `${k}=${typeof x === "object" ? JSON.stringify(x) : String(x)}`).join(", ");
  const [text, setText] = useState(show(value));
  useEffect(() => setText(show(value)), [JSON.stringify(value)]); // eslint-disable-line react-hooks/exhaustive-deps
  return (
    <input aria-label="Arguments" value={text} disabled={disabled} placeholder="book=$case.book, cob=$case.cob"
      onChange={(e) => setText(e.target.value)}
      onBlur={() => onChange(Object.fromEntries(text.split(",").map((p) => p.split("=")).filter(([k]) => k?.trim())
        .map(([k, ...v]) => [k.trim(), literal(v.join("=").trim())])))}
      className={clsx(input, mono, "min-w-[14rem]")} />
  );
}

/** Literal from a text box: numbers and true/false become values; anything else stays text. */
export function literal(s: string): unknown {
  const t = s.trim();
  if (/^-?\d+(\.\d+)?$/.test(t)) return Number(t);
  if (t === "true" || t === "false") return t === "true";
  return s;
}

function ToolPicker({ value, onChange, access, tools, disabled, multiple, id }: {
  value: string | string[] | null; onChange: (v: string | string[] | null) => void; access: "read" | "write";
  tools: Ctx["tools"]; disabled: boolean; multiple?: boolean; id?: string;
}) {
  const choices = tools.filter((t) => t.access === access);
  const known = new Set(choices.map((t) => t.name));
  if (!multiple) {
    const v = (value as string | null) ?? "";
    return (
      <select id={id} value={v} disabled={disabled} onChange={(e) => onChange(e.target.value || null)} className={input}>
        <option value="">— choose a {access} tool —</option>
        {v && !known.has(v) && <option value={v}>{v} (not onboarded)</option>}
        {choices.map((t) => <option key={t.name} value={t.name}>{t.name} — {t.description}</option>)}
      </select>
    );
  }
  const list = (value as string[] | null) ?? [];
  return (
    <div className="flex flex-wrap gap-1.5">
      {[...choices.map((t) => t.name), ...list.filter((n) => !known.has(n))].map((n) => {
        const on = list.includes(n);
        return (
          <button
            key={n}
            type="button"
            disabled={disabled}
            aria-pressed={on}
            title={choices.find((t) => t.name === n)?.description ?? "not an onboarded tool"}
            onClick={() => onChange(on ? list.filter((x) => x !== n) : [...list, n])}
            className={clsx("rounded-full border px-2 py-0.5 font-mono text-[11px]",
              on ? "border-primary-300 bg-primary-50 text-primary-800" : "border-surface-200 text-surface-500 hover:border-surface-300",
              !known.has(n) && "border-red-300 text-red-700", disabled && "cursor-not-allowed opacity-70")}
          >
            {n}
          </button>
        );
      })}
    </div>
  );
}

function Cell({ col, value, onChange, disabled, ctx }: { col: Column; value: unknown; onChange: (v: unknown) => void; disabled: boolean; ctx: Ctx }) {
  const kind = col.kind ?? "text";
  if (kind === "bool") return <input type="checkbox" aria-label={col.label} checked={!!value} disabled={disabled} onChange={(e) => onChange(e.target.checked)} />;
  if (kind === "select") {
    return (
      <select aria-label={col.label} value={String(value ?? "")} disabled={disabled} onChange={(e) => onChange(e.target.value)} className={clsx(input, "min-w-[6rem]")}>
        {!opts(col.options ?? [], ctx.m).some((o) => o.value === value) && <option value={String(value ?? "")}>{String(value ?? "—")}</option>}
        {opts(col.options ?? [], ctx.m).map((o) => <option key={o.value} value={o.value}>{o.label ?? o.value}</option>)}
      </select>
    );
  }
  if (kind === "list") return <ListInput value={(value as string[]) ?? []} onChange={onChange} disabled={disabled} />;
  if (kind === "args") return <ArgsInput value={(value as Json) ?? {}} onChange={onChange} disabled={disabled} />;
  if (kind === "tool") return <ToolPicker value={(value as string) ?? null} onChange={onChange} access={col.access ?? "read"} tools={ctx.tools} disabled={disabled} />;
  if (kind === "tools") {
    const only = col.within ? new Set((get(ctx.m, col.within) as string[]) ?? []) : null;
    return <ToolPicker value={(value as string[]) ?? []} onChange={onChange} access={col.access ?? "read"} tools={only ? ctx.tools.filter((t) => only.has(t.name)) : ctx.tools} disabled={disabled} multiple />;
  }
  if (kind === "number") return <input type="number" aria-label={col.label} value={value === null || value === undefined ? "" : String(value)} disabled={disabled} onChange={(e) => onChange(e.target.value === "" ? null : Number(e.target.value))} className={clsx(input, "w-24")} />;
  if (kind === "textarea") return <textarea aria-label={col.label} value={String(value ?? "")} rows={3} disabled={disabled} onChange={(e) => onChange(e.target.value)} className={input} />;
  return (
    <input
      aria-label={col.label}
      value={String(value ?? "")}
      disabled={disabled}
      onChange={(e) => onChange(e.target.value)}
      className={clsx(input, kind === "expr" && mono, col.wide ? "min-w-[16rem]" : "min-w-[5rem]")}
    />
  );
}

const rowGet = (row: Json, key: string) => get(row, key);
function rowSet(row: Json, key: string, v: unknown): Json {
  const [h, ...rest] = key.split(".");
  return { ...row, [h]: rest.length ? rowSet((row[h] as Json) ?? {}, rest.join("."), v) : v };
}

function Table({ columns, rows, onChange, disabled, ctx, addLabel, newRow, keyCol }: {
  columns: Column[]; rows: Json[]; onChange: (rows: Json[]) => void; disabled: boolean; ctx: Ctx;
  addLabel: string; newRow: Json; keyCol?: Column;
}) {
  const cols = keyCol ? [keyCol, ...columns] : columns;
  return (
    <div>
      <div className="overflow-x-auto rounded-lg border border-surface-200">
        <table className="min-w-full text-xs">
          <thead className="bg-surface-50 text-left text-[11px] uppercase tracking-wider text-surface-500">
            <tr>{cols.map((c) => <th key={c.key} className="px-2 py-1.5 font-semibold">{c.label}</th>)}<th className="w-8" /></tr>
          </thead>
          <tbody className="divide-y divide-surface-100">
            {rows.length === 0 && <tr><td colSpan={cols.length + 1} className="px-2 py-3 text-center text-surface-400">None yet.</td></tr>}
            {rows.map((row, i) => (
              <tr key={i} className="align-top">
                {cols.map((c) => (
                  <td key={c.key} className="px-1.5 py-1">
                    <Cell col={c} value={rowGet(row, c.key)} disabled={disabled} ctx={ctx}
                      onChange={(v) => onChange(rows.map((r, j) => (j === i ? rowSet(r, c.key, v) : r)))} />
                  </td>
                ))}
                <td className="px-1 py-1">
                  {!disabled && (
                    <button type="button" aria-label="Remove" onClick={() => onChange(rows.filter((_, j) => j !== i))} className="rounded p-1 text-surface-400 hover:bg-red-50 hover:text-red-600">
                      <Trash2 size={13} />
                    </button>
                  )}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
      {!disabled && (
        <button type="button" onClick={() => onChange([...rows, structuredClone(newRow)])} className="mt-1.5 inline-flex items-center gap-1 rounded-lg border border-dashed border-surface-300 px-2 py-1 text-xs text-surface-600 hover:border-primary-300 hover:text-primary-700">
          <Plus size={12} /> {addLabel}
        </button>
      )}
    </div>
  );
}

function Kv({ value, onChange, disabled, keyLabel, valueLabel }: { value: Json; onChange: (v: Json) => void; disabled: boolean; keyLabel: string; valueLabel: string }) {
  const rows = Object.entries(value ?? {}).map(([k, v]) => ({ k, v: typeof v === "object" ? JSON.stringify(v) : String(v ?? "") }));
  const write = (next: { k: string; v: string }[]) => onChange(Object.fromEntries(next.filter((r) => r.k !== "").map((r) => [r.k, literal(r.v)])));
  return (
    <Table
      columns={[{ key: "k", label: keyLabel }, { key: "v", label: valueLabel, wide: true }]}
      rows={rows}
      onChange={(r) => write(r as { k: string; v: string }[])}
      disabled={disabled}
      ctx={{ m: {}, tools: [], locked: () => null, set: () => {} }}
      addLabel={`Add ${keyLabel.toLowerCase()}`}
      newRow={{ k: "", v: "" }}
    />
  );
}

function Locked({ why }: { why: string }) {
  return <span className="ml-1 inline-flex items-center gap-0.5 text-[10px] font-normal text-surface-400" title={why}><Lock size={10} /> {why}</span>;
}

/** One configuration field, with its label, help and lock. */
export function Field({ spec, ctx }: { spec: FieldSpec; ctx: Ctx }) {
  if (spec.when && !spec.when(ctx.m)) return null;
  const why = ctx.locked(spec.path);
  const disabled = !!why;
  const value = get(ctx.m, spec.path);
  const set = (v: unknown) => ctx.set(spec.path, v);
  const id = `f-${spec.path.replace(/\W/g, "-")}`;
  const label = (
    <span className="flex flex-wrap items-center text-xs font-medium text-surface-700">
      {spec.label}{why && <Locked why={why} />}
    </span>
  );
  const help = spec.help && <span className="mt-0.5 block text-[11px] font-normal leading-snug text-surface-500">{spec.help}</span>;

  if (spec.kind === "object") {
    const on = value !== null && value !== undefined;
    return (
      <fieldset className="rounded-lg border border-surface-200 p-3">
        <legend className="px-1">{label}</legend>
        <label className="flex items-center gap-2 text-xs text-surface-700">
          <input type="checkbox" checked={on} disabled={disabled} onChange={(e) => set(e.target.checked ? structuredClone(spec.empty) : null)} />
          {spec.toggle}
        </label>
        {help}
        {on && (
          <div className="mt-2 grid gap-3 sm:grid-cols-2">
            {spec.fields.map((f) => <Field key={f.path} spec={{ ...f, path: `${spec.path}.${f.path}` } as FieldSpec} ctx={ctx} />)}
          </div>
        )}
      </fieldset>
    );
  }

  if (spec.kind === "bool") {
    return (
      <label className="flex items-start gap-2 text-xs text-surface-700">
        <input id={id} type="checkbox" className="mt-0.5" checked={!!value} disabled={disabled} onChange={(e) => set(e.target.checked)} />
        <span>{label}{help}</span>
      </label>
    );
  }

  let control: React.ReactNode;
  switch (spec.kind) {
    case "text": case "template": case "cron": case "time":
      control = <input id={id} type={spec.kind === "time" ? "time" : "text"} value={String(value ?? "")} placeholder={spec.placeholder} disabled={disabled}
        onChange={(e) => set(e.target.value === "" ? null : e.target.value)} className={clsx(input, (spec.kind === "cron" || spec.kind === "template") && mono)} />;
      break;
    case "expr":
      control = <input id={id} value={String(value ?? "")} placeholder={spec.placeholder ?? "e.g. abs(total) > policy.materiality_threshold"} disabled={disabled}
        onChange={(e) => set(e.target.value === "" ? null : e.target.value)} className={clsx(input, mono)} />;
      break;
    case "textarea":
      control = <textarea id={id} value={String(value ?? "")} rows={8} disabled={disabled} onChange={(e) => set(e.target.value)} className={clsx(input, "leading-relaxed")} />;
      break;
    case "number":
      control = <input id={id} type="number" min={spec.min} max={spec.max} step={spec.step ?? "any"} value={value === null || value === undefined ? "" : String(value)}
        disabled={disabled} onChange={(e) => set(e.target.value === "" ? (spec.nullable ? null : 0) : Number(e.target.value))} className={clsx(input, "w-40")} />;
      break;
    case "select": {
      const o = opts(spec.options, ctx.m);
      control = (
        <select id={id} value={String(value ?? "")} disabled={disabled} onChange={(e) => set(e.target.value === "" ? null : e.target.value)} className={input}>
          {(spec.nullable || !o.some((x) => x.value === value)) && <option value="">{spec.nullable ? "— none —" : String(value ?? "—")}</option>}
          {o.map((x) => <option key={x.value} value={x.value}>{x.label ?? x.value}</option>)}
        </select>
      );
      break;
    }
    case "multi": {
      const list = (value as string[]) ?? [];
      control = (
        <div className="grid gap-1 sm:grid-cols-2">
          {opts(spec.options, ctx.m).map((o) => (
            <label key={o.value} className="flex items-center gap-2 text-xs text-surface-700">
              <input type="checkbox" checked={list.includes(o.value)} disabled={disabled}
                onChange={(e) => set(e.target.checked ? [...list, o.value] : list.filter((x) => x !== o.value))} />
              {o.label ?? o.value}
            </label>
          ))}
        </div>
      );
      break;
    }
    case "list":
      control = <ListInput id={id} value={(value as string[]) ?? []} onChange={set} disabled={disabled} placeholder={spec.placeholder} />;
      break;
    case "tool":
      control = <ToolPicker id={id} value={(value as string) ?? null} onChange={set} access={spec.access} tools={ctx.tools} disabled={disabled} />;
      break;
    case "tools":
      control = <ToolPicker value={(value as string[]) ?? []} onChange={set} access={spec.access} tools={ctx.tools} disabled={disabled} multiple />;
      break;
    case "kv":
      control = <Kv value={(value as Json) ?? {}} onChange={set} disabled={disabled} keyLabel={spec.keyLabel} valueLabel={spec.valueLabel} />;
      break;
    case "rows":
      control = <Table columns={typeof spec.columns === "function" ? spec.columns(ctx.m) : spec.columns} rows={(value as Json[]) ?? []} onChange={set} disabled={disabled} ctx={ctx} addLabel={spec.addLabel} newRow={spec.newRow} />;
      break;
    case "dict": {
      const entries = Object.entries((value as Record<string, Json>) ?? {}).map(([k, v]) => ({ __key: k, ...v }));
      control = (
        <Table
          keyCol={{ key: "__key", label: spec.keyLabel }}
          columns={spec.columns}
          rows={entries}
          onChange={(rows) => set(Object.fromEntries(rows.map(({ __key, ...rest }) => [String(__key ?? ""), rest])))}
          disabled={disabled}
          ctx={ctx}
          addLabel={spec.addLabel}
          newRow={{ __key: "", ...spec.newEntry }}
        />
      );
      break;
    }
    case "matrix": {
      const rows = Object.keys((get(ctx.m, spec.rows) as Json) ?? {});
      const cols = ((get(ctx.m, spec.cols) as string[]) ?? []);
      const table = (value as Record<string, Record<string, string>>) ?? {};
      const o = opts(spec.options, ctx.m);
      control = rows.length === 0 ? <p className="text-xs text-surface-400">Add categories first.</p> : (
        <div className="overflow-x-auto rounded-lg border border-surface-200">
          <table className="text-xs">
            <thead className="bg-surface-50 text-[11px] uppercase tracking-wider text-surface-500">
              <tr><th className="px-2 py-1.5 text-left">Category</th>{cols.map((c) => <th key={c} className="px-2 py-1.5 text-left">{c}</th>)}</tr>
            </thead>
            <tbody className="divide-y divide-surface-100">
              {rows.map((r) => (
                <tr key={r}>
                  <td className="px-2 py-1 font-medium text-surface-700">{r} <span className="font-normal text-surface-500">{String(get(ctx.m, `${spec.rows}.${r}.name`) ?? "")}</span></td>
                  {cols.map((c) => (
                    <td key={c} className="px-1.5 py-1">
                      <select aria-label={`${r} ${c}`} value={table[r]?.[c] ?? ""} disabled={disabled} className={clsx(input, "min-w-[8rem]")}
                        onChange={(e) => {
                          const row = { ...(table[r] ?? {}) };
                          if (e.target.value) row[c] = e.target.value; else delete row[c];
                          set({ ...table, [r]: row });
                        }}>
                        <option value="">— model decides —</option>
                        {o.map((x) => <option key={x.value} value={x.value}>{x.label ?? x.value}</option>)}
                      </select>
                    </td>
                  ))}
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      );
      break;
    }
    case "policy": {
      const policy = (value as Record<string, { value: unknown; unit?: string | null }>) ?? {};
      const rows = Object.entries(policy).map(([k, p]) => ({ name: k, value: p.value === null || p.value === undefined ? "" : String(p.value), unit: p.unit ?? "" }));
      control = (
        <Table
          columns={[{ key: "name", label: "Threshold" }, { key: "value", label: "Value (empty = not confirmed)" }, { key: "unit", label: "Unit" }]}
          rows={rows}
          onChange={(next) => set(Object.fromEntries(next.filter((r) => r.name !== "").map((r) => [String(r.name), {
            value: String(r.value ?? "").trim() === "" ? null : literal(String(r.value)),
            unit: String(r.unit ?? "").trim() || null,
          }])))}
          disabled={disabled}
          ctx={ctx}
          addLabel="Add threshold"
          newRow={{ name: "", value: "", unit: "" }}
        />
      );
      break;
    }
  }

  const wide = ["rows", "dict", "matrix", "policy", "kv", "tools", "multi", "textarea"].includes(spec.kind);
  // A single control gets a real <label>; a table or a set of choices is a labelled group.
  return wide ? (
    <div role="group" aria-label={spec.label} className="sm:col-span-2">
      {label}
      <div className="mt-1">{control}</div>
      {help}
    </div>
  ) : (
    <div>
      <label htmlFor={id}>{label}</label>
      <div className="mt-1">{control}</div>
      {help}
    </div>
  );
}
