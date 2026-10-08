// Configure the orchestrator, step by step: the pipeline on the left (each
// step on or off, where the run stops for a person, the gates locked on), the
// selected step's settings on the right. Every edit is checked by the server
// as you go; nothing changes until you submit and a second owner approves.
//
// The same editor serves a capability's owners (everything) and a team
// group's owners (only the capability's `configurable` paths; the rest is
// shown, locked).

import { useEffect, useMemo, useState } from "react";
import clsx from "clsx";
import { stringify } from "yaml";
import { AlertTriangle, CheckCircle2, Hand, Loader2, Lock, Power, Send, Undo2 } from "lucide-react";

import { useConfigCheck, useDraftGroup, usePlatform, useSubmitDraft, type GroupConfig } from "../../api/aof";
import { ErrorState } from "../ui";
import { Field, type Ctx } from "./fields";
import { allowed, changedPaths, get, groupSet, preview, setPath, type Json } from "./paths";
import { STAGES, STEP_ORDER, stageOf, stagesFor, type Stage } from "./stages";
import PrepareSteps, { dataSteps } from "./PrepareSteps";

type Mode = { kind: "capability" } | { kind: "group"; config: GroupConfig; configurable: string[] };

function useDebounced<T>(value: T, ms: number): T {
  const [v, setV] = useState(value);
  useEffect(() => {
    const t = setTimeout(() => setV(value), ms);
    return () => clearTimeout(t);
  }, [value, ms]);
  return v;
}

const stepsOf = (m: Json) => (get(m, "steps") as string[]) ?? [];
const pausesOf = (m: Json) => (get(m, "pause_before") as string[]) ?? [];

/** The field paths a stage edits, to tell which stages hold changes. */
const stagePaths = (s: Stage) => s.custom === "prepare" ? ["step_settings"]
  : s.fields.map((f) => f.path).concat(s.step ? [`tollgates.${s.step}`] : []);

function isOn(m: Json, s: Stage): boolean {
  if (s.id === "source") return true;
  if (s.custom === "prepare") return dataSteps(m).length > 0;
  return !s.step || stepsOf(m).includes(s.step);
}

/** Switch a core step on or off, keeping configurable steps where they are. */
export function withCoreStep(steps: string[], step: string, on: boolean): string[] {
  if (!on) return steps.filter((x) => x !== step);
  if (steps.includes(step)) return steps;
  const rank = STEP_ORDER.indexOf(step);
  const after = steps.findIndex((x) => STEP_ORDER.includes(x) && STEP_ORDER.indexOf(x) > rank);
  return after < 0 ? [...steps, step] : [...steps.slice(0, after), step, ...steps.slice(after)];
}

function switchStep(m: Json, s: Stage, on: boolean): Json {
  let out = setPath(m, "steps", withCoreStep(stepsOf(m), s.step!, on));
  if (on) out = s.onEnable ? s.onEnable(out) : out;
  else {
    out = setTollgate(out, s.step!, false);
    for (const c of s.clears ?? []) out = setPath(out, c.path, c.value);
  }
  return out;
}

/** Put a tollgate before `step`, or take it away (the stop and its settings go together). */
function setTollgate(m: Json, step: string, on: boolean): Json {
  const gates = { ...((get(m, "tollgates") as Json) ?? {}) };
  if (on) gates[step] = gates[step] ?? { roles: [], check: "", stop_needs_comment: true };
  else delete gates[step];
  const pauses = pausesOf(m).filter((x) => x !== step);
  return setPath(setPath(m, "tollgates", gates), "pause_before", on ? [...pauses, step] : pauses);
}

function switchSource(m: Json, to: "load" | "match"): Json {
  const steps = stepsOf(m).map((x) => (x === "load" || x === "match" ? to : x));
  let out = setPath(m, "steps", steps);
  if (to === "match") {
    out = setPath(out, "items.load", null);
    if (!get(out, "match")) {
      out = setPath(out, "match", { left: { tool: "", args: {} }, right: { tool: "", args: {} }, keys: [], amount_field: "amount", tolerance: 0, left_label: "left", right_label: "right" });
    }
  } else {
    out = setPath(out, "match", null);
    if (!get(out, "items.load")) out = setPath(out, "items.load", { tool: "", args: {} });
  }
  return out;
}

export default function OrchestratorEditor({ capabilityId, manifest, mode, canEdit }: {
  capabilityId: string;
  /** The configuration as it runs today (for a group: merged with its settings). */
  manifest: Json;
  mode: Mode;
  canEdit: boolean;
}) {
  const platform = usePlatform();
  const [working, setWorking] = useState<Json>(manifest);
  const [stageId, setStageId] = useState("case");
  const [note, setNote] = useState("");
  const [reviewing, setReviewing] = useState(false);
  useEffect(() => setWorking(manifest), [manifest]);

  const isGroup = mode.kind === "group";
  const stages = stagesFor(STAGES.filter((s) => !(isGroup && s.capabilityOnly)), working);
  const stage = stages.find((s) => s.id === stageId) ?? stages[0];

  const locked = (path: string): string | null => {
    if (!canEdit) return "owners change this";
    // a group may edit a field when it, or something inside it (policy.*), is configurable
    if (isGroup && !allowed(mode.configurable, path) && !mode.configurable.some((c) => c.startsWith(`${path}.`))) return "set by the capability";
    return null;
  };
  const ctx: Ctx = {
    m: working,
    tools: (platform.data?.connectors ?? []).flatMap((c) => c.tools),
    locked,
    set: (path, value) => setWorking((w) => setPath(w, path, value)),
  };

  const changes = useMemo(() => changedPaths(manifest, working), [manifest, working]);
  const set = useMemo(
    () => (mode.kind === "group" ? groupSet(mode.config.set as Json, mode.configurable, manifest, working) : null),
    [mode, manifest, working],
  );
  const debounced = useDebounced(working, 500);
  const body = useMemo(() => {
    if (!canEdit) return null;
    if (mode.kind === "capability") return { manifest: debounced };
    return { config: { ...mode.config, set: groupSet(mode.config.set as Json, mode.configurable, manifest, debounced) } };
  }, [canEdit, mode, manifest, debounced]);
  const check = useConfigCheck(capabilityId, body);
  const checking = check.isFetching || debounced !== working;
  const problems = check.data?.problems ?? [];
  const byStage = useMemo(() => {
    const out: Record<string, string[]> = {};
    for (const p of problems) (out[stageOf(p)] ??= []).push(p);
    return out;
  }, [problems]);

  const submitCap = useSubmitDraft();
  const submitGroup = useDraftGroup(capabilityId);
  const submitting = submitCap.isPending || submitGroup.isPending;
  const submitError = submitCap.error ?? submitGroup.error;
  const done = submitCap.data ? `Version ${submitCap.data.version} drafted. Another owner approves it under Versions or in Authoring.`
    : submitGroup.data ? `Version ${submitGroup.data.version} of this group drafted. Another group owner approves it under Versions.` : null;
  const submit = () => {
    const n = note || `orchestrator: ${[...new Set(changes.map((c) => c.split(".")[0]))].join(", ")}`;
    if (mode.kind === "capability") submitCap.mutate({ yaml: stringify(working), note: n });
    else submitGroup.mutate({ config: { ...mode.config, set: set! }, note: n });
  };

  const stepLocked = locked("steps");
  const pauseLocked = locked("pause_before");
  const steps = stepsOf(working);
  const pauses = pausesOf(working);
  const toggled = (s: Stage) => !!s.step && (["steps", "pause_before"] as const).some(
    (k) => ((get(manifest, k) as string[]) ?? []).includes(s.step!) !== ((get(working, k) as string[]) ?? []).includes(s.step!));
  const changedIn = (s: Stage) => toggled(s)
    || changes.some((c) => stagePaths(s).some((p) => c === p || c.startsWith(`${p}.`) || p.startsWith(`${c}.`)));

  return (
    <div className="space-y-3">
      {/* Status: what changed, whether it passes, and the way to submit */}
      <div className="sticky top-0 z-10 flex flex-wrap items-center gap-2 rounded-xl border border-surface-200 bg-card px-3 py-2 text-sm shadow-sm">
        <span className="font-medium text-surface-800">{changes.length ? `${changes.length} change${changes.length > 1 ? "s" : ""}` : "No changes"}</span>
        {canEdit && (
          checking ? <span className="inline-flex items-center gap-1 text-xs text-surface-500"><Loader2 size={12} className="animate-spin" /> Checking…</span>
          : check.error ? <span className="text-xs text-surface-500">Checks need the live service.</span>
          : problems.length === 0 ? <span className="inline-flex items-center gap-1 text-xs text-green-700"><CheckCircle2 size={13} /> Passes every platform check</span>
          : <span className="inline-flex items-center gap-1 text-xs text-red-700"><AlertTriangle size={13} /> {problems.length} problem{problems.length > 1 ? "s" : ""} to fix</span>
        )}
        {!canEdit && <span className="text-xs text-surface-500">You can look; its owners change it.</span>}
        {canEdit && changes.length > 0 && (
          <div className="ml-auto flex gap-2">
            <button type="button" onClick={() => { setWorking(manifest); setReviewing(false); }} className="inline-flex items-center gap-1 rounded-lg border border-surface-300 px-2.5 py-1 text-xs text-surface-700 hover:bg-surface-50">
              <Undo2 size={12} /> Discard
            </button>
            <button type="button" onClick={() => setReviewing(true)} className="inline-flex items-center gap-1 rounded-lg bg-brand px-3 py-1 text-xs font-medium text-brand-fg hover:bg-brand-strong">
              <Send size={12} /> Review and submit
            </button>
          </div>
        )}
      </div>

      {byStage.pipeline && (
        <ul className="rounded-lg border border-red-200 bg-red-50 px-3 py-2 text-xs text-red-800">
          {byStage.pipeline.map((p) => <li key={p}>{p}</li>)}
        </ul>
      )}

      <div className="grid gap-3 lg:grid-cols-[17rem_minmax(0,1fr)]">
        {/* The pipeline */}
        <nav aria-label="Orchestrator steps" className="flex gap-1.5 overflow-x-auto rounded-xl border border-surface-200 bg-card p-2 lg:flex-col lg:overflow-visible">
          {stages.map((s) => {
            const on = isOn(working, s);
            const n = byStage[s.id]?.length ?? 0;
            return (
              <button
                key={s.id}
                type="button"
                aria-current={s.id === stage.id ? "step" : undefined}
                onClick={() => setStageId(s.id)}
                className={clsx("flex min-w-[10rem] shrink-0 items-center gap-2 rounded-lg px-2.5 py-2 text-left text-sm lg:min-w-0",
                  s.id === stage.id ? "bg-primary-50 text-primary-900 ring-1 ring-primary-200" : "text-surface-700 hover:bg-surface-50",
                  !on && "opacity-55")}
              >
                <span className={clsx("h-2 w-2 shrink-0 rounded-full", s.gate ? "bg-surface-500" : on ? "bg-green-500" : "bg-surface-300")} />
                <span className="min-w-0 flex-1 truncate">{s.title}</span>
                {s.step && pauses.includes(s.step) && <Hand size={12} className="shrink-0 text-amber-600" aria-label="stops for a person" />}
                {s.gate && <Lock size={11} className="shrink-0 text-surface-400" aria-label="always on" />}
                {changedIn(s) && <span className="h-1.5 w-1.5 shrink-0 rounded-full bg-primary-500" aria-label="changed" />}
                {n > 0 && <span className="shrink-0 rounded-full bg-red-100 px-1.5 text-[10px] font-semibold text-red-700">{n}</span>}
              </button>
            );
          })}
        </nav>

        {/* The selected step */}
        <section aria-label={stage.title} className="min-w-0 rounded-xl border border-surface-200 bg-card p-4">
          <div className="flex flex-wrap items-start gap-3">
            <div className="min-w-0 flex-1">
              <h3 className="flex items-center gap-2 text-base font-semibold text-surface-900">
                {stage.title}
                {stage.step && <code className="rounded bg-surface-100 px-1.5 py-0.5 text-[11px] font-normal text-surface-600">{stage.step}</code>}
                {stage.gate && <span className="inline-flex items-center gap-1 rounded-full bg-surface-100 px-2 py-0.5 text-[11px] font-normal text-surface-600"><Lock size={10} /> always on</span>}
              </h3>
              <p className="mt-1 text-sm text-surface-600">{stage.says}</p>
            </div>
            {stage.optional && (
              <label className={clsx("inline-flex items-center gap-2 rounded-lg border px-2.5 py-1.5 text-xs", isOn(working, stage) ? "border-green-200 bg-green-50 text-green-800" : "border-surface-200 text-surface-600")}>
                <Power size={12} />
                <input type="checkbox" checked={isOn(working, stage)} disabled={!!stepLocked} onChange={(e) => setWorking((w) => switchStep(w, stage, e.target.checked))} />
                This step runs
              </label>
            )}
          </div>

          {stage.id === "source" && (
            <div className="mt-3 flex flex-wrap gap-2 text-xs" role="radiogroup" aria-label="Item source">
              {(["match", "load"] as const).map((k) => (
                <label key={k} className={clsx("inline-flex items-center gap-2 rounded-lg border px-2.5 py-1.5", steps.includes(k) ? "border-primary-300 bg-primary-50 text-primary-900" : "border-surface-200 text-surface-600")}>
                  <input type="radio" name="source" checked={steps.includes(k)} disabled={!!stepLocked} onChange={() => setWorking((w) => switchSource(w, k))} />
                  {k === "match" ? "Two systems, matched to each other" : "One system"}
                </label>
              ))}
            </div>
          )}

          {stage.step && !stage.gate && isOn(working, stage) && stage.step !== "publish" && stage.step !== steps[0] && (
            <div className={clsx("mt-3 rounded-lg border p-3", pauses.includes(stage.step) ? "border-amber-200 bg-amber-50/60" : "border-surface-200")}>
              <label className="inline-flex items-center gap-2 text-xs font-medium text-surface-800">
                <input type="checkbox" checked={pauses.includes(stage.step)} disabled={!!pauseLocked}
                  onChange={(e) => setWorking((w) => setTollgate(w, stage.step!, e.target.checked))} />
                <Hand size={12} className="text-amber-600" /> Tollgate: a person approves the work so far before this step
              </label>
              <p className="mt-0.5 text-[11px] text-surface-500">
                The run waits here. The person sees what the earlier steps produced, then continues the run or stops it with a reason.
              </p>
              {pauses.includes(stage.step) && (
                <div className="mt-3 grid gap-3 sm:grid-cols-2">
                  <Field ctx={{ ...ctx, locked: () => pauseLocked }} spec={{ kind: "list", path: `tollgates.${stage.step}.roles`, label: "Passed by (roles)", help: "Empty = the capability's reviewers." }} />
                  <Field ctx={{ ...ctx, locked: () => pauseLocked }} spec={{ kind: "text", path: `tollgates.${stage.step}.check`, label: "What they check", placeholder: "e.g. Are both sides complete for the COB?" }} />
                  <Field ctx={{ ...ctx, locked: () => pauseLocked }} spec={{ kind: "bool", path: `tollgates.${stage.step}.stop_needs_comment`, label: "Stopping the run needs a reason" }} />
                </div>
              )}
            </div>
          )}
          {(stage.step === "review" || (stage.step === "publish" && isOn(working, stage))) && (
            <p className="mt-3 inline-flex items-center gap-1.5 text-xs text-surface-600"><Hand size={12} className="text-amber-600" /> The run always stops here for a person.</p>
          )}
          {(stepLocked && stage.step && (stage.optional || stage.id === "source")) && (
            <p className="mt-2 text-[11px] text-surface-500"><Lock size={10} className="mr-0.5 inline" /> Which steps run is {isGroup ? "set by the capability" : "for its owners to change"}.</p>
          )}

          {byStage[stage.id] && (
            <ul className="mt-3 space-y-0.5 rounded-lg border border-red-200 bg-red-50 px-3 py-2 text-xs text-red-800">
              {byStage[stage.id].map((p) => <li key={p}>{p}</li>)}
            </ul>
          )}

          {stage.custom === "prepare" ? (
            <PrepareSteps ctx={ctx} setWorking={setWorking} stepsLocked={stepLocked} />
          ) : isOn(working, stage) ? (
            stage.fields.length === 0 ? (
              <p className="mt-4 text-sm text-surface-500">Nothing to set: this gate works the same for every capability.</p>
            ) : stage.fields.some((f) => !f.when || f.when(working)) ? (
              <div className="mt-4 grid gap-4 sm:grid-cols-2">
                {stage.fields.map((f) => <Field key={f.path} spec={f} ctx={ctx} />)}
              </div>
            ) : (
              <div className="mt-4 text-sm text-surface-500">
                <p>Nothing is set for this step here{isGroup ? "" : "; team groups may set it for themselves"}.</p>
                {stage.onEnable && !locked(stage.fields[0].path.split(".")[0]) && (
                  <button type="button" onClick={() => setWorking((w) => stage.onEnable!(w))} className="mt-2 rounded-lg border border-primary-300 px-3 py-1.5 text-xs font-medium text-primary-700 hover:bg-primary-50">
                    Set up this step
                  </button>
                )}
              </div>
            )
          ) : (
            <p className="mt-4 text-sm text-surface-500">This step is off. Switch it on to configure it.</p>
          )}
        </section>
      </div>

      {reviewing && changes.length > 0 && (
        <section aria-label="Review changes" className="rounded-xl border border-primary-200 bg-card p-4">
          <h3 className="text-sm font-semibold text-surface-900">What changes</h3>
          <ul className="mt-2 divide-y divide-surface-100 rounded-lg border border-surface-200 text-xs">
            {changes.map((p) => (
              <li key={p} className="grid gap-1 px-3 py-1.5 sm:grid-cols-[minmax(0,14rem)_minmax(0,1fr)]">
                <code className="truncate text-surface-600">{p}</code>
                <span className="text-surface-700"><span className="text-surface-400 line-through">{preview(get(manifest, p))}</span> → <span className="font-medium">{preview(get(working, p))}</span></span>
              </li>
            ))}
          </ul>
          <div className="mt-3 flex flex-wrap items-end gap-2">
            <label className="min-w-[14rem] flex-1 text-xs font-medium text-surface-600">
              Note for the approver
              <input value={note} onChange={(e) => setNote(e.target.value)} className="mt-1 block w-full rounded-lg border border-surface-300 bg-card px-2 py-1.5 text-sm font-normal" />
            </label>
            <button type="button" onClick={submit} disabled={submitting || problems.length > 0 || checking}
              className="inline-flex items-center gap-2 rounded-lg bg-brand px-4 py-2 text-sm font-medium text-brand-fg hover:bg-brand-strong disabled:opacity-50">
              <Send size={14} /> Submit for approval
            </button>
          </div>
          {problems.length > 0 && <p className="mt-2 text-xs text-red-700">Fix the problems first; they are listed on the steps marked in red.</p>}
          {!!submitError && <div className="mt-2"><ErrorState error={submitError} /></div>}
          {done && <p className="mt-2 text-sm text-green-700">{done}</p>}
        </section>
      )}
    </div>
  );
}
