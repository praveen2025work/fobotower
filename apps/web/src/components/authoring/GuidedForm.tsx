// Authoring without a model: a few plain questions build a capability's
// configuration. The platform's validator judges it exactly as it judges a
// model's draft, and another owner approves it before it goes live.

import { useState } from "react";
import { ListChecks } from "lucide-react";

import { usePlatform, type DraftResult } from "../../api/helix";

const KINDS = [
  { value: "investigate", label: "Investigate what another system found", help: "e.g. MB Rec's breaks: no matching, Agent One Finance explains each one" },
  { value: "reconcile", label: "Match two systems", help: "e.g. bank vs ledger: Agent One Finance matches, then explains what does not match" },
  { value: "commentary", label: "Explain variances", help: "e.g. actual vs budget: what is material gets commentary" },
  { value: "review", label: "Review a list", help: "e.g. attestations or exceptions, one decision per group" },
] as const;

const list = (s: string) => s.split(/[,\n]/).map((x) => x.trim()).filter(Boolean);
const input = "mt-1 block w-full rounded-lg border border-surface-300 bg-card px-2 py-1.5 text-sm font-normal";
const label = "block text-xs font-medium text-surface-600";

export default function GuidedForm({ onBuild, pending }: { onBuild: (answers: Record<string, unknown>) => void; pending: boolean }) {
  const platform = usePlatform();
  const readTools = (platform.data?.connectors ?? []).flatMap((c) => c.tools).filter((t) => t.access === "read");
  const [a, setA] = useState({
    name: "", description: "", kind: "investigate", case_key: "book, cob", scope_field: "", case_label: "Run", item_label: "Item",
    source_tool: "", left_tool: "", right_tool: "", left_label: "left", right_label: "right", match_keys: "", id_field: "",
    amount_field: "", measure: "actual", baseline: "budget", display: "", materiality: "", unit: "GBP", materiality_unconfirmed: false,
    group_by: "", decided_by: "model_then_person", model_tools: [] as string[], instructions: "", tollgate: false, tollgate_check: "",
    opens: "manual", late_items: false, reviewer_roles: "", owner_role: "", ask: "", checklist: "", follow_through: false,
    sample_size: "", clock_hours: "", clock_starts: "", authority_tool: "", two_approvers_over: "",
    reserved_roles: "", reserved_when: "", reserved_reason: "",
  });
  const set = (k: keyof typeof a, v: unknown) => setA((x) => ({ ...x, [k]: v }));
  const key = list(a.case_key);
  const tool = (k: "source_tool" | "left_tool" | "right_tool", text: string) => (
    <label className={label}>{text}
      <select aria-label={text} value={a[k]} onChange={(e) => set(k, e.target.value)} className={input}>
        <option value="">Choose a connector tool…</option>
        {readTools.map((t) => <option key={t.name} value={t.name}>{t.name} — {t.description}</option>)}
      </select>
    </label>
  );
  const build = () => onBuild({
    ...a, case_key: key, display: list(a.display), group_by: list(a.group_by), match_keys: list(a.match_keys),
    reviewer_roles: list(a.reviewer_roles), checklist: a.checklist.split("\n").map((q) => q.trim()).filter(Boolean),
    materiality: a.materiality === "" ? null : Number(a.materiality),
    sample_size: a.sample_size === "" ? null : Number(a.sample_size),
    clock_hours: a.clock_hours === "" ? null : Number(a.clock_hours),
    clock_starts: a.clock_starts.trim() || null,
    two_approvers_over: a.two_approvers_over === "" ? null : Number(a.two_approvers_over),
    reserved_roles: list(a.reserved_roles),
    ask_targets: a.ask.split("\n").map((l) => l.split(":")).filter((p) => p.length === 2 && p[0].trim())
      .map(([n, r]) => ({ name: n.trim(), roles: list(r) })),
  });

  return (
    <div className="space-y-3">
      <label className={label}>Name<input value={a.name} onChange={(e) => set("name", e.target.value)} placeholder="Equities breaks" className={input} /></label>
      <label className={label}>What it is for<input value={a.description} onChange={(e) => set("description", e.target.value)} className={input} /></label>

      <fieldset>
        <legend className={label}>What kind of work</legend>
        <div className="mt-1 grid gap-1.5 sm:grid-cols-2">
          {KINDS.map((k) => (
            <label key={k.value} className={`flex cursor-pointer gap-2 rounded-lg border p-2 text-xs ${a.kind === k.value ? "border-primary-400 bg-primary-50" : "border-surface-200"}`}>
              <input type="radio" name="kind" checked={a.kind === k.value} onChange={() => set("kind", k.value)} />
              <span><span className="font-medium text-surface-800">{k.label}</span><br /><span className="text-surface-500">{k.help}</span></span>
            </label>
          ))}
        </div>
      </fieldset>

      <div className="grid gap-3 sm:grid-cols-2">
        <label className={label}>One case is one… (key fields)<input value={a.case_key} onChange={(e) => set("case_key", e.target.value)} placeholder="book, cob" className={input} /></label>
        <label className={label}>Who sees a case is limited by
          <select aria-label="Data scope field" value={a.scope_field} onChange={(e) => set("scope_field", e.target.value)} className={input}>
            <option value="">no data scope</option>{key.map((k) => <option key={k}>{k}</option>)}
          </select>
        </label>
        <label className={label}>A case is called<input value={a.case_label} onChange={(e) => set("case_label", e.target.value)} className={input} /></label>
        <label className={label}>An item is called<input value={a.item_label} onChange={(e) => set("item_label", e.target.value)} className={input} /></label>
      </div>

      {a.kind === "reconcile" ? (
        <div className="grid gap-3 sm:grid-cols-2">
          {tool("left_tool", "First system")}
          {tool("right_tool", "Second system")}
          <label className={label}>First system is called<input value={a.left_label} onChange={(e) => set("left_label", e.target.value)} className={input} /></label>
          <label className={label}>Second system is called<input value={a.right_label} onChange={(e) => set("right_label", e.target.value)} className={input} /></label>
          <label className={label}>Match on<input value={a.match_keys} onChange={(e) => set("match_keys", e.target.value)} placeholder="ref" className={input} /></label>
          <label className={label}>Amount field<input value={a.amount_field} onChange={(e) => set("amount_field", e.target.value)} placeholder="amount" className={input} /></label>
        </div>
      ) : (
        <div className="grid gap-3 sm:grid-cols-2">
          {tool("source_tool", "Items come from")}
          <label className={label}>Item id field<input value={a.id_field} onChange={(e) => set("id_field", e.target.value)} placeholder="instrument" className={input} /></label>
          {a.kind === "commentary" ? (
            <>
              <label className={label}>Actual field<input value={a.measure} onChange={(e) => set("measure", e.target.value)} className={input} /></label>
              <label className={label}>Compared with<input value={a.baseline} onChange={(e) => set("baseline", e.target.value)} className={input} /></label>
            </>
          ) : (
            <label className={label}>Amount field<input value={a.amount_field} onChange={(e) => set("amount_field", e.target.value)} placeholder="difference" className={input} /></label>
          )}
        </div>
      )}

      <div className="grid gap-3 sm:grid-cols-3">
        <label className={label}>Material from<input type="number" value={a.materiality} onChange={(e) => set("materiality", e.target.value)} placeholder="none" className={input} /></label>
        <label className={label}>Unit<input value={a.unit} onChange={(e) => set("unit", e.target.value)} className={input} /></label>
        <label className="flex items-end gap-1.5 pb-2 text-xs text-surface-600">
          <input type="checkbox" checked={a.materiality_unconfirmed} onChange={(e) => set("materiality_unconfirmed", e.target.checked)} /> Threshold not confirmed yet
        </label>
      </div>
      <div className="grid gap-3 sm:grid-cols-2">
        <label className={label}>Group items by<input value={a.group_by} onChange={(e) => set("group_by", e.target.value)} placeholder="break_type" className={input} /></label>
        <label className={label}>Columns reviewers see<input value={a.display} onChange={(e) => set("display", e.target.value)} placeholder="instrument, desk, difference" className={input} /></label>
      </div>

      <fieldset className="rounded-lg border border-surface-200 p-2">
        <legend className={`${label} px-1`}>What rules cannot settle goes to</legend>
        <div className="flex flex-wrap gap-4 text-xs">
          <label className="flex items-center gap-1.5"><input type="radio" name="decided_by" checked={a.decided_by === "model_then_person"} onChange={() => set("decided_by", "model_then_person")} /> the model, then a person</label>
          <label className="flex items-center gap-1.5"><input type="radio" name="decided_by" checked={a.decided_by === "person"} onChange={() => set("decided_by", "person")} /> a person (no model)</label>
        </div>
        {a.decided_by === "model_then_person" && (
          <div className="mt-2 space-y-2">
            <p className="text-xs text-surface-600">Tools the model may read:</p>
            <div className="flex flex-wrap gap-x-3 gap-y-1 text-xs">
              {readTools.map((t) => (
                <label key={t.name} className="flex items-center gap-1">
                  <input type="checkbox" checked={a.model_tools.includes(t.name)}
                    onChange={(e) => set("model_tools", e.target.checked ? [...a.model_tools, t.name] : a.model_tools.filter((x) => x !== t.name))} />
                  <span className="font-mono">{t.name}</span>
                </label>
              ))}
            </div>
            <label className={label}>Instructions to the model (optional)<textarea value={a.instructions} onChange={(e) => set("instructions", e.target.value)} rows={3} className={input} /></label>
            <label className="flex items-center gap-1.5 text-xs text-surface-600">
              <input type="checkbox" checked={a.tollgate} onChange={(e) => set("tollgate", e.target.checked)} /> A person approves the work before the model is asked (tollgate)
            </label>
            {a.tollgate && <label className={label}>What they check<input value={a.tollgate_check} onChange={(e) => set("tollgate_check", e.target.value)} className={input} /></label>}
          </div>
        )}
      </fieldset>

      <div className="grid gap-3 sm:grid-cols-2">
        <label className={label}>Reviewers (roles)<input value={a.reviewer_roles} onChange={(e) => set("reviewer_roles", e.target.value)} placeholder="FOBO_CONTROLLER" className={input} /></label>
        <label className={label}>Owners (role, optional)<input value={a.owner_role} onChange={(e) => set("owner_role", e.target.value)} className={input} /></label>
        <label className={label}>A case opens
          <select aria-label="A case opens" value={a.opens} onChange={(e) => set("opens", e.target.value)} className={input}>
            <option value="manual">when someone opens it</option>
            <option value="event">when another system notifies Agent One Finance</option>
            <option value="schedule">on a schedule</option>
          </select>
        </label>
        <div className="flex flex-col justify-end gap-1 pb-1 text-xs text-surface-600">
          {a.opens === "event" && (
            <label className="flex items-center gap-1.5"><input type="checkbox" checked={a.late_items} onChange={(e) => set("late_items", e.target.checked)} /> Late items open a follow-up case</label>
          )}
          {key.length >= 2 && (
            <label className="flex items-center gap-1.5"><input type="checkbox" checked={a.follow_through} onChange={(e) => set("follow_through", e.target.checked)} /> Re-check each decision on the next {key[key.length - 1]}</label>
          )}
        </div>
      </div>
      <label className={label}>Who reviewers may ask for evidence (one per line: Name: ROLE)
        <textarea value={a.ask} onChange={(e) => set("ask", e.target.value)} rows={2} placeholder={"Desk (trader): EQ_DESK\nOperations: OPS"} className={input} />
      </label>
      <label className={label}>Sign-off checklist (one question per line)
        <textarea value={a.checklist} onChange={(e) => set("checklist", e.target.value)} rows={3} placeholder="Is the root cause evidenced?" className={input} />
      </label>
      <fieldset className="rounded-lg border border-surface-200 p-3">
        <legend className={`${label} px-1`}>Controls (optional)</legend>
        <div className="grid gap-3 sm:grid-cols-2">
          <label className={label}>Review a random sample of
            <input type="number" min={1} value={a.sample_size} onChange={(e) => set("sample_size", e.target.value)} placeholder="all items" className={input} />
          </label>
          <label className={label}>Service level (hours)
            <input type="number" min={1} value={a.clock_hours} onChange={(e) => set("clock_hours", e.target.value)} placeholder="none" className={input} />
          </label>
          {a.clock_hours !== "" && (
            <label className={label}>…counted from the field
              <input value={a.clock_starts} onChange={(e) => set("clock_starts", e.target.value)} placeholder="when the case opens" className={input} />
            </label>
          )}
          <label className={label}>Who may approve how much: the bank's authority system
            <select aria-label="Authority from" value={a.authority_tool} onChange={(e) => set("authority_tool", e.target.value)} className={input}>
              <option value="">not used</option>
              {readTools.map((t) => <option key={t.name} value={t.name}>{t.name} — {t.description}</option>)}
            </select>
          </label>
          {!a.authority_tool && (
            <label className={label}>…or two different approvers from (amount)
              <input type="number" min={0} value={a.two_approvers_over} onChange={(e) => set("two_approvers_over", e.target.value)} placeholder="never" className={input} />
            </label>
          )}
          <label className={label}>Decisions reserved for (roles)
            <input value={a.reserved_roles} onChange={(e) => set("reserved_roles", e.target.value)} placeholder="CREDIT_OFFICER" className={input} />
          </label>
          {a.reserved_roles.trim() && (
            <>
              <label className={label}>…when
                <input value={a.reserved_when} onChange={(e) => set("reserved_when", e.target.value)} placeholder="abs(total) > 1000000" className={input} />
              </label>
              <label className={label}>…because
                <input value={a.reserved_reason} onChange={(e) => set("reserved_reason", e.target.value)} placeholder="credit decisions" className={input} />
              </label>
            </>
          )}
        </div>
      </fieldset>
      <button onClick={build} disabled={pending || !a.name.trim()}
        className="inline-flex items-center gap-2 rounded-lg bg-brand px-4 py-2 text-sm font-medium text-brand-fg hover:bg-brand-strong disabled:opacity-50">
        <ListChecks size={14} /> {pending ? "Building…" : "Build the capability"}
      </button>
    </div>
  );
}

export type { DraftResult };
