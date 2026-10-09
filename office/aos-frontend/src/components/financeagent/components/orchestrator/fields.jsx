// Generated from apps/web/src/components/orchestrator/fields.tsx by apps/web/office/convert.mjs. Office changes to this file are
// kept by aof_sync.py on the next update; see docs/agent-one-finance/office/conversion-guide.md.
// Reusable form controls for configuration, driven by a field description
// (stages.ts). Each control reads and writes one dotted path of the working
// manifest; a control the owner may not change is shown, locked, with why.

import { useEffect, useState } from "react";
import clsx from "clsx";
import { Lock, Plus, Trash2 } from "lucide-react";

import { get } from "./paths";

/** One column of a table (rows, dict). */
const input =
  "block w-full rounded-lg border border-surface-300 bg-card px-2 py-1.5 text-sm text-surface-800 disabled:bg-surface-100 disabled:text-surface-500";
const mono = "font-mono text-xs";

const opts = (o, m) => (typeof o === "function" ? o(m) : o);

/** A comma-separated list that keeps what the user is typing until they leave the box. */
function ListInput({ value, onChange, disabled, placeholder, id }) {
  const [text, setText] = useState(value.join(", "));
  useEffect(() => setText(value.join(", ")), [value.join("|")]); // eslint-disable-line react-hooks/exhaustive-deps
  return (
    <input
      id={id}
      value={text}
      disabled={disabled}
      placeholder={placeholder ?? "comma-separated"}
      onChange={(e) => setText(e.target.value)}
      onBlur={() =>
        onChange(
          text
            .split(",")
            .map((s) => s.trim())
            .filter(Boolean),
        )
      }
      className={input}
    />
  );
}

/** Tool arguments as one line, "book=$case.book, cob=$case.cob", kept as typed until the box is left. */
function ArgsInput({ value, onChange, disabled }) {
  const show = (v) =>
    Object.entries(v ?? {})
      .map(([k, x]) => `${k}=${typeof x === "object" ? JSON.stringify(x) : String(x)}`)
      .join(", ");
  const [text, setText] = useState(show(value));
  useEffect(() => setText(show(value)), [JSON.stringify(value)]); // eslint-disable-line react-hooks/exhaustive-deps
  return (
    <input
      aria-label="Arguments"
      value={text}
      disabled={disabled}
      placeholder="book=$case.book, cob=$case.cob"
      onChange={(e) => setText(e.target.value)}
      onBlur={() =>
        onChange(
          Object.fromEntries(
            text
              .split(",")
              .map((p) => p.split("="))
              .filter(([k]) => k?.trim())
              .map(([k, ...v]) => [k.trim(), literal(v.join("=").trim())]),
          ),
        )
      }
      className={clsx(input, mono, "min-w-[14rem]")}
    />
  );
}

/** Literal from a text box: numbers and true/false become values; anything else stays text. */
export function literal(s) {
  const t = s.trim();
  if (/^-?\d+(\.\d+)?$/.test(t)) return Number(t);
  if (t === "true" || t === "false") return t === "true";
  return s;
}

function ToolPicker({ value, onChange, access, tools, disabled, multiple, id }) {
  const choices = tools.filter((t) => t.access === access);
  const known = new Set(choices.map((t) => t.name));
  if (!multiple) {
    const v = value ?? "";
    return (
      <select
        id={id}
        value={v}
        disabled={disabled}
        onChange={(e) => onChange(e.target.value || null)}
        className={input}
      >
        <option value="">— choose a {access} tool —</option>
        {v && !known.has(v) && <option value={v}>{v} (not onboarded)</option>}
        {choices.map((t) => (
          <option key={t.name} value={t.name}>
            {t.name} — {t.description}
          </option>
        ))}
      </select>
    );
  }
  return <ToolSet value={value ?? []} onChange={onChange} choices={choices} known={known} disabled={disabled} />;
}

/** Several tools: the chosen ones as chips, and "Add a tool" — a search over the
 *  rest, grouped by the system they belong to — so a long catalogue never hides
 *  what is actually selected. */
export function ToolSet({ value, onChange, choices, known = new Set(choices.map((t) => t.name)), disabled = false }) {
  const [open, setOpen] = useState(false);
  const [q, setQ] = useState("");
  const describe = (n) => choices.find((t) => t.name === n)?.description ?? "not an onboarded tool";
  const rest = choices.filter(
    (t) => !value.includes(t.name) && (!q || `${t.name} ${t.description}`.toLowerCase().includes(q.toLowerCase())),
  );
  const bySystem = rest.reduce((acc, t) => {
    const sys = t.name.split(".")[0];
    (acc[sys] ??= []).push(t);
    return acc;
  }, {});
  return (
    <div>
      <div className="flex flex-wrap items-center gap-1.5">
        {value.length === 0 && <span className="text-xs text-surface-400">None chosen.</span>}
        {value.map((n) => (
          <span
            key={n}
            title={describe(n)}
            className={clsx(
              "inline-flex items-center gap-1 rounded-full border py-0.5 pl-2 pr-1 font-mono text-[11px]",
              known.has(n) ? "border-primary-300 bg-primary-50 text-primary-800" : "border-red-300 text-red-700",
            )}
          >
            {n}
            {!disabled && (
              <button
                type="button"
                aria-label={`Remove ${n}`}
                onClick={() => onChange(value.filter((x) => x !== n))}
                className="rounded-full px-1 text-surface-500 hover:bg-surface-100 hover:text-surface-800"
              >
                ×
              </button>
            )}
          </span>
        ))}
        {!disabled && (
          <button
            type="button"
            onClick={() => setOpen(!open)}
            aria-expanded={open}
            className="rounded-full border border-dashed border-surface-300 px-2 py-0.5 text-[11px] font-medium text-surface-600 hover:border-primary-300 hover:text-primary-700"
          >
            + Add a tool
          </button>
        )}
      </div>
      {open && !disabled && (
        <div className="mt-2 rounded-lg border border-surface-200 bg-card p-2 shadow-sm">
          <input
            autoFocus
            value={q}
            onChange={(e) => setQ(e.target.value)}
            placeholder="Search tools, e.g. trades or MOTIF"
            aria-label="Search tools"
            className={input}
          />
          <div className="mt-2 max-h-64 space-y-2 overflow-y-auto">
            {Object.keys(bySystem).length === 0 && (
              <p className="px-1 text-xs text-surface-400">Nothing else matches.</p>
            )}
            {Object.entries(bySystem).map(([sys, tools]) => (
              <div key={sys}>
                <p className="px-1 text-[10px] font-semibold uppercase tracking-wide text-surface-400">{sys}</p>
                {tools.map((t) => (
                  <button
                    key={t.name}
                    type="button"
                    onClick={() => onChange([...value, t.name])}
                    className="flex w-full items-baseline gap-2 rounded px-1 py-1 text-left hover:bg-surface-50"
                  >
                    <code className="shrink-0 text-[11px] text-surface-800">{t.name}</code>
                    <span className="truncate text-[11px] text-surface-500">{t.description}</span>
                  </button>
                ))}
              </div>
            ))}
          </div>
        </div>
      )}
    </div>
  );
}

function Cell({ col, value, onChange, disabled, ctx }) {
  const kind = col.kind ?? "text";
  if (kind === "bool")
    return (
      <input
        type="checkbox"
        aria-label={col.label}
        checked={!!value}
        disabled={disabled}
        onChange={(e) => onChange(e.target.checked)}
      />
    );
  if (kind === "select") {
    return (
      <select
        aria-label={col.label}
        value={String(value ?? "")}
        disabled={disabled}
        onChange={(e) => onChange(e.target.value)}
        className={clsx(input, "min-w-[6rem]")}
      >
        {!opts(col.options ?? [], ctx.m).some((o) => o.value === value) && (
          <option value={String(value ?? "")}>{String(value ?? "—")}</option>
        )}
        {opts(col.options ?? [], ctx.m).map((o) => (
          <option key={o.value} value={o.value}>
            {o.label ?? o.value}
          </option>
        ))}
      </select>
    );
  }
  if (kind === "list") return <ListInput value={value ?? []} onChange={onChange} disabled={disabled} />;
  if (kind === "args") return <ArgsInput value={value ?? {}} onChange={onChange} disabled={disabled} />;
  if (kind === "tool")
    return (
      <ToolPicker
        value={value ?? null}
        onChange={onChange}
        access={col.access ?? "read"}
        tools={ctx.tools}
        disabled={disabled}
      />
    );
  if (kind === "tools") {
    const only = col.within ? new Set(get(ctx.m, col.within) ?? []) : null;
    return (
      <ToolPicker
        value={value ?? []}
        onChange={onChange}
        access={col.access ?? "read"}
        tools={only ? ctx.tools.filter((t) => only.has(t.name)) : ctx.tools}
        disabled={disabled}
        multiple
      />
    );
  }
  if (kind === "number")
    return (
      <input
        type="number"
        aria-label={col.label}
        value={value === null || value === undefined ? "" : String(value)}
        disabled={disabled}
        onChange={(e) => onChange(e.target.value === "" ? null : Number(e.target.value))}
        className={clsx(input, "w-24")}
      />
    );
  if (kind === "textarea")
    return (
      <textarea
        aria-label={col.label}
        value={String(value ?? "")}
        rows={3}
        disabled={disabled}
        onChange={(e) => onChange(e.target.value)}
        className={input}
      />
    );
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

const rowGet = (row, key) => get(row, key);
function rowSet(row, key, v) {
  const [h, ...rest] = key.split(".");
  return { ...row, [h]: rest.length ? rowSet(row[h] ?? {}, rest.join("."), v) : v };
}

function Table({ columns, rows, onChange, disabled, ctx, addLabel, newRow, keyCol }) {
  const cols = keyCol ? [keyCol, ...columns] : columns;
  return (
    <div>
      <div className="overflow-x-auto rounded-lg border border-surface-200">
        <table className="min-w-full text-xs">
          <thead className="bg-surface-50 text-left text-[11px] uppercase tracking-wider text-surface-500">
            <tr>
              {cols.map((c) => (
                <th key={c.key} className="px-2 py-1.5 font-semibold">
                  {c.label}
                </th>
              ))}
              <th className="w-8" />
            </tr>
          </thead>
          <tbody className="divide-y divide-surface-100">
            {rows.length === 0 && (
              <tr>
                <td colSpan={cols.length + 1} className="px-2 py-3 text-center text-surface-400">
                  None yet.
                </td>
              </tr>
            )}
            {rows.map((row, i) => (
              <tr key={i} className="align-top">
                {cols.map((c) => (
                  <td key={c.key} className="px-1.5 py-1">
                    <Cell
                      col={c}
                      value={rowGet(row, c.key)}
                      disabled={disabled}
                      ctx={ctx}
                      onChange={(v) => onChange(rows.map((r, j) => (j === i ? rowSet(r, c.key, v) : r)))}
                    />
                  </td>
                ))}
                <td className="px-1 py-1">
                  {!disabled && (
                    <button
                      type="button"
                      aria-label="Remove"
                      onClick={() => onChange(rows.filter((_, j) => j !== i))}
                      className="rounded p-1 text-surface-400 hover:bg-red-50 hover:text-red-600"
                    >
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
        <button
          type="button"
          onClick={() => onChange([...rows, structuredClone(newRow)])}
          className="mt-1.5 inline-flex items-center gap-1 rounded-lg border border-dashed border-surface-300 px-2 py-1 text-xs text-surface-600 hover:border-primary-300 hover:text-primary-700"
        >
          <Plus size={12} /> {addLabel}
        </button>
      )}
    </div>
  );
}

function Kv({ value, onChange, disabled, keyLabel, valueLabel }) {
  const rows = Object.entries(value ?? {}).map(([k, v]) => ({
    k,
    v: typeof v === "object" ? JSON.stringify(v) : String(v ?? ""),
  }));
  const write = (next) => onChange(Object.fromEntries(next.filter((r) => r.k !== "").map((r) => [r.k, literal(r.v)])));
  return (
    <Table
      columns={[
        { key: "k", label: keyLabel },
        { key: "v", label: valueLabel, wide: true },
      ]}
      rows={rows}
      onChange={(r) => write(r)}
      disabled={disabled}
      ctx={{ m: {}, tools: [], locked: () => null, set: () => {} }}
      addLabel={`Add ${keyLabel.toLowerCase()}`}
      newRow={{ k: "", v: "" }}
    />
  );
}

function Locked({ why }) {
  return (
    <span className="ml-1 inline-flex items-center gap-0.5 text-[10px] font-normal text-surface-400" title={why}>
      <Lock size={10} /> {why}
    </span>
  );
}

/** One configuration field, with its label, help and lock. */
export function Field({ spec, ctx }) {
  if (spec.when && !spec.when(ctx.m)) return null;
  const why = ctx.locked(spec.path);
  const disabled = !!why;
  const value = get(ctx.m, spec.path);
  const set = (v) => ctx.set(spec.path, v);
  const id = `f-${spec.path.replace(/\W/g, "-")}`;
  const label = (
    <span className="flex flex-wrap items-center text-xs font-medium text-surface-700">
      {spec.label}
      {why && <Locked why={why} />}
    </span>
  );
  const help = spec.help && (
    <span className="mt-0.5 block text-[11px] font-normal leading-snug text-surface-500">{spec.help}</span>
  );

  if (spec.kind === "object") {
    const on = value !== null && value !== undefined;
    return (
      <fieldset className="rounded-lg border border-surface-200 p-3">
        <legend className="px-1">{label}</legend>
        <label className="flex items-center gap-2 text-xs text-surface-700">
          <input
            type="checkbox"
            checked={on}
            disabled={disabled}
            onChange={(e) => set(e.target.checked ? structuredClone(spec.empty) : null)}
          />
          {spec.toggle}
        </label>
        {help}
        {on && (
          <div className="mt-2 grid gap-3 sm:grid-cols-2">
            {spec.fields.map((f) => (
              <Field key={f.path} spec={{ ...f, path: `${spec.path}.${f.path}` }} ctx={ctx} />
            ))}
          </div>
        )}
      </fieldset>
    );
  }

  if (spec.kind === "bool") {
    return (
      <label className="flex items-start gap-2 text-xs text-surface-700">
        <input
          id={id}
          type="checkbox"
          className="mt-0.5"
          checked={!!value}
          disabled={disabled}
          onChange={(e) => set(e.target.checked)}
        />
        <span>
          {label}
          {help}
        </span>
      </label>
    );
  }

  let control;
  switch (spec.kind) {
    case "text":
    case "template":
    case "cron":
    case "time":
      control = (
        <input
          id={id}
          type={spec.kind === "time" ? "time" : "text"}
          value={String(value ?? "")}
          placeholder={spec.placeholder}
          disabled={disabled}
          onChange={(e) => set(e.target.value === "" ? null : e.target.value)}
          className={clsx(input, (spec.kind === "cron" || spec.kind === "template") && mono)}
        />
      );
      break;
    case "expr":
      control = (
        <input
          id={id}
          value={String(value ?? "")}
          placeholder={spec.placeholder ?? "e.g. abs(total) > policy.materiality_threshold"}
          disabled={disabled}
          onChange={(e) => set(e.target.value === "" ? null : e.target.value)}
          className={clsx(input, mono)}
        />
      );
      break;
    case "textarea":
      control = (
        <textarea
          id={id}
          value={String(value ?? "")}
          rows={8}
          disabled={disabled}
          onChange={(e) => set(e.target.value)}
          className={clsx(input, "leading-relaxed")}
        />
      );
      break;
    case "number":
      control = (
        <input
          id={id}
          type="number"
          min={spec.min}
          max={spec.max}
          step={spec.step ?? "any"}
          value={value === null || value === undefined ? "" : String(value)}
          disabled={disabled}
          onChange={(e) => set(e.target.value === "" ? (spec.nullable ? null : 0) : Number(e.target.value))}
          className={clsx(input, "w-40")}
        />
      );
      break;
    case "select": {
      const o = opts(spec.options, ctx.m);
      control = (
        <select
          id={id}
          value={String(value ?? "")}
          disabled={disabled}
          onChange={(e) => set(e.target.value === "" ? null : e.target.value)}
          className={input}
        >
          {(spec.nullable || !o.some((x) => x.value === value)) && (
            <option value="">{spec.nullable ? "— none —" : String(value ?? "—")}</option>
          )}
          {o.map((x) => (
            <option key={x.value} value={x.value}>
              {x.label ?? x.value}
            </option>
          ))}
        </select>
      );
      break;
    }
    case "multi": {
      const list = value ?? [];
      control = (
        <div className="grid gap-1 sm:grid-cols-2">
          {opts(spec.options, ctx.m).map((o) => (
            <label key={o.value} className="flex items-center gap-2 text-xs text-surface-700">
              <input
                type="checkbox"
                checked={list.includes(o.value)}
                disabled={disabled}
                onChange={(e) => set(e.target.checked ? [...list, o.value] : list.filter((x) => x !== o.value))}
              />
              {o.label ?? o.value}
            </label>
          ))}
        </div>
      );
      break;
    }
    case "list":
      control = (
        <ListInput id={id} value={value ?? []} onChange={set} disabled={disabled} placeholder={spec.placeholder} />
      );
      break;
    case "tool":
      control = (
        <ToolPicker
          id={id}
          value={value ?? null}
          onChange={set}
          access={spec.access}
          tools={ctx.tools}
          disabled={disabled}
        />
      );
      break;
    case "tools":
      control = (
        <ToolPicker
          value={value ?? []}
          onChange={set}
          access={spec.access}
          tools={ctx.tools}
          disabled={disabled}
          multiple
        />
      );
      break;
    case "kv":
      control = (
        <Kv
          value={value ?? {}}
          onChange={set}
          disabled={disabled}
          keyLabel={spec.keyLabel}
          valueLabel={spec.valueLabel}
        />
      );
      break;
    case "rows":
      control = (
        <Table
          columns={typeof spec.columns === "function" ? spec.columns(ctx.m) : spec.columns}
          rows={value ?? []}
          onChange={set}
          disabled={disabled}
          ctx={ctx}
          addLabel={spec.addLabel}
          newRow={spec.newRow}
        />
      );
      break;
    case "dict": {
      const entries = Object.entries(value ?? {}).map(([k, v]) => ({ __key: k, ...v }));
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
      const rows = Object.keys(get(ctx.m, spec.rows) ?? {});
      const cols = get(ctx.m, spec.cols) ?? [];
      const table = value ?? {};
      const o = opts(spec.options, ctx.m);
      control =
        rows.length === 0 ? (
          <p className="text-xs text-surface-400">Add categories first.</p>
        ) : (
          <div className="overflow-x-auto rounded-lg border border-surface-200">
            <table className="text-xs">
              <thead className="bg-surface-50 text-[11px] uppercase tracking-wider text-surface-500">
                <tr>
                  <th className="px-2 py-1.5 text-left">Category</th>
                  {cols.map((c) => (
                    <th key={c} className="px-2 py-1.5 text-left">
                      {c}
                    </th>
                  ))}
                </tr>
              </thead>
              <tbody className="divide-y divide-surface-100">
                {rows.map((r) => (
                  <tr key={r}>
                    <td className="px-2 py-1 font-medium text-surface-700">
                      {r}{" "}
                      <span className="font-normal text-surface-500">
                        {String(get(ctx.m, `${spec.rows}.${r}.name`) ?? "")}
                      </span>
                    </td>
                    {cols.map((c) => (
                      <td key={c} className="px-1.5 py-1">
                        <select
                          aria-label={`${r} ${c}`}
                          value={table[r]?.[c] ?? ""}
                          disabled={disabled}
                          className={clsx(input, "min-w-[8rem]")}
                          onChange={(e) => {
                            const row = { ...(table[r] ?? {}) };
                            if (e.target.value) row[c] = e.target.value;
                            else delete row[c];
                            set({ ...table, [r]: row });
                          }}
                        >
                          <option value="">— model decides —</option>
                          {o.map((x) => (
                            <option key={x.value} value={x.value}>
                              {x.label ?? x.value}
                            </option>
                          ))}
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
      const policy = value ?? {};
      const rows = Object.entries(policy).map(([k, p]) => ({
        name: k,
        value: p.value === null || p.value === undefined ? "" : String(p.value),
        unit: p.unit ?? "",
      }));
      control = (
        <Table
          columns={[
            { key: "name", label: "Threshold" },
            { key: "value", label: "Value (empty = not confirmed)" },
            { key: "unit", label: "Unit" },
          ]}
          rows={rows}
          onChange={(next) =>
            set(
              Object.fromEntries(
                next
                  .filter((r) => r.name !== "")
                  .map((r) => [
                    String(r.name),
                    {
                      value: String(r.value ?? "").trim() === "" ? null : literal(String(r.value)),
                      unit: String(r.unit ?? "").trim() || null,
                    },
                  ]),
              ),
            )
          }
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
