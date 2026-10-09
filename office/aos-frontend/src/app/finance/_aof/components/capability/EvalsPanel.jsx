// Generated from apps/web/src/components/capability/EvalsPanel.tsx by apps/web/office/convert.mjs. Office changes to this file are
// kept by aof_sync.py on the next update; see office/README.md.
// Evals: try a version (a draft before approving it, or the live one after a
// model or instruction change) on cases people already decided. Each is
// replayed in a hidden copy — same connectors, nothing written, nobody
// notified — and its proposals are compared with what people decided.

import { useState } from "react";
import clsx from "clsx";
import { ChevronDown, ChevronRight, GitCompare, History, Play, Scale } from "lucide-react";

import { useEvalAvailable, useEvalRun, useEvals, useStartEval } from "../../api/aof";
import StatusBadge from "../StatusBadge";
import { Empty, ErrorState, Fold, Loading, formatTime } from "../ui";

const pct = (v) => (v == null ? "—" : `${Math.round(v * 100)}%`);

const OUTCOMES = {
  agree: {
    label: "agreed",
    means: "proposed what people approved, or escalated what they rejected",
    tone: "text-green-700",
  },
  disagree: { label: "disagreed", means: "proposed what people rejected", tone: "text-red-700" },
  escalated: {
    label: "escalated",
    means: "sent to a person where people had approved: safe, but less automation",
    tone: "text-orange-700",
  },
  missing: {
    label: "missing",
    means: "groups people decided that this version did not produce",
    tone: "text-surface-700",
  },
  new: { label: "new", means: "groups this version produced that were not there before", tone: "text-surface-700" },
};

const HOW = [
  {
    icon: GitCompare,
    title: "Choose a version",
    text: "A draft before you approve it, or the live one after a model or instruction change.",
  },
  {
    icon: History,
    title: "Replay past cases",
    text: "Cases people already decided are run again in hidden copies: same connectors, nothing written, nobody notified.",
  },
  {
    icon: Scale,
    title: "Compare with people",
    text: "Each proposal is set against what people decided, in their words. The result is below, and in Phoenix.",
  },
];

function Result({ r }) {
  const [open, setOpen] = useState(false);
  const detail = useEvalRun(open ? r.run_id : null);
  const s = r.summary;
  if (!s || s.cases === undefined) return null;
  const rate = s.agreement_rate;
  const diffs = (detail.data?.results ?? []).flatMap((c) =>
    c.groups.filter((g) => g.outcome !== "agree").map((g) => ({ case_id: c.case_id, g })),
  );
  return (
    <div className="mt-2 space-y-2">
      <div className="flex flex-wrap items-center gap-x-4 gap-y-1">
        <p className="text-sm text-surface-700">
          <span className="text-2xl font-bold tabular-nums text-surface-900">{pct(rate)}</span> agree with people
        </p>
        <p className="text-xs text-surface-500">
          {s.groups_compared} decisions in {s.cases} past {s.cases === 1 ? "case" : "cases"}
          {s.verdict_match_rate != null && ` · same verdict ${pct(s.verdict_match_rate)}`}
          {s.wording_mean != null && ` · wording ${pct(s.wording_mean)} alike`}
          {` · model cost $${s.cost_usd.toFixed(2)}`}
        </p>
      </div>
      {rate != null && (
        <div className="flex h-2 overflow-hidden rounded-full bg-surface-100" aria-hidden>
          {["agree", "escalated", "disagree"].map((o) => {
            const n = s[o];
            return n ? (
              <span
                key={o}
                className={clsx(o === "agree" ? "bg-green-600" : o === "escalated" ? "bg-orange-400" : "bg-red-500")}
                style={{ width: `${(n / Math.max(1, s.groups_compared)) * 100}%` }}
              />
            ) : null;
          })}
        </div>
      )}
      <ul className="flex flex-wrap gap-x-4 gap-y-1 text-xs">
        {Object.keys(OUTCOMES)
          .filter((o) => s[o] > 0)
          .map((o) => (
            <li key={o} title={OUTCOMES[o].means}>
              <b className={clsx("font-semibold", OUTCOMES[o].tone)}>{s[o]}</b> {OUTCOMES[o].label}
            </li>
          ))}
      </ul>
      {s.groups_compared + s.missing + s.new > s.agree && (
        <button
          onClick={() => setOpen(!open)}
          className="inline-flex items-center gap-1 text-xs font-medium text-primary-700 hover:underline"
        >
          {open ? <ChevronDown size={12} /> : <ChevronRight size={12} />} Where it differed from people
        </button>
      )}
      {open && detail.isLoading && <Loading what="differences" />}
      {open &&
        detail.data &&
        (diffs.length === 0 ? (
          <p className="text-xs text-surface-500">Nothing differed.</p>
        ) : (
          <ul className="divide-y divide-surface-100 rounded-lg border border-surface-200 text-xs">
            {diffs.map(({ case_id, g }, i) => (
              <li key={i} className="grid gap-1 px-3 py-2 sm:grid-cols-[12rem_1fr_1fr]">
                <div>
                  <p className="font-medium text-surface-900">{g.group}</p>
                  <p className={clsx("font-semibold", OUTCOMES[g.outcome].tone)}>{OUTCOMES[g.outcome].label}</p>
                  <p className="font-mono text-[10px] text-surface-400">{case_id}</p>
                </div>
                <div>
                  <p className="text-[10px] font-semibold uppercase tracking-wide text-surface-500">People decided</p>
                  {g.expected ? (
                    <p className="text-surface-700">
                      {g.expected.action}
                      {g.expected.verdict && ` · ${g.expected.verdict.replace(/_/g, " ")}`} — “{g.expected.words}”{" "}
                      <span className="text-surface-500">({g.expected.decided_by})</span>
                    </p>
                  ) : (
                    <p className="text-surface-400">not there before</p>
                  )}
                </div>
                <div>
                  <p className="text-[10px] font-semibold uppercase tracking-wide text-surface-500">
                    This version proposes
                  </p>
                  {g.now ? (
                    <p className="text-surface-700">
                      {g.now.status}
                      {g.now.verdict && ` · ${g.now.verdict.replace(/_/g, " ")}`}
                      {(g.now.comment || g.now.reason) && ` — ${g.now.comment || g.now.reason}`}
                    </p>
                  ) : (
                    <p className="text-surface-400">nothing</p>
                  )}
                </div>
              </li>
            ))}
          </ul>
        ))}
    </div>
  );
}

export default function EvalsPanel({ capabilityId, versions, groups, statuses = {}, groupNames = {} }) {
  const runs = useEvals(capabilityId);
  const start = useStartEval(capabilityId);
  const [version, setVersion] = useState("");
  const [group, setGroup] = useState(groups[0] ?? "");
  const available = useEvalAvailable(capabilityId, groups.length ? group : null);
  const ready = available.data?.cases;
  const name = (g) => (g ? (groupNames[g] ?? g) : "");

  return (
    <div className="space-y-5">
      <ol className="grid gap-2 sm:grid-cols-3" aria-label="How an eval works">
        {HOW.map((h, i) => (
          <li key={h.title} className="rounded-lg border border-surface-200 p-3">
            <p className="flex items-center gap-1.5 text-sm font-semibold text-surface-900">
              <span className="flex h-5 w-5 items-center justify-center rounded-full bg-surface-700 text-[10px] font-bold text-white">
                {i + 1}
              </span>
              <h.icon size={13} className="text-primary-600" /> {h.title}
            </p>
            <p className="mt-1 text-xs text-surface-600">{h.text}</p>
          </li>
        ))}
      </ol>

      <div className="rounded-lg border border-primary-200 bg-primary-50/40 p-3">
        <div className="flex flex-wrap items-end gap-3 text-xs">
          <label className="text-surface-600">
            Version to try
            <select
              aria-label="Eval version"
              value={version}
              onChange={(e) => setVersion(e.target.value ? Number(e.target.value) : "")}
              className="mt-1 block rounded-md border border-surface-300 bg-card px-2 py-1.5 text-sm"
            >
              <option value="">the live version</option>
              {[...versions]
                .sort((a, b) => b - a)
                .map((v) => (
                  <option key={v} value={v}>
                    v{v}
                    {statuses[v] ? ` · ${statuses[v] === "active" ? "live" : statuses[v]}` : ""}
                  </option>
                ))}
            </select>
          </label>
          {groups.length > 0 && (
            <label className="text-surface-600">
              Team group
              <select
                aria-label="Eval group"
                value={group}
                onChange={(e) => setGroup(e.target.value)}
                className="mt-1 block rounded-md border border-surface-300 bg-card px-2 py-1.5 text-sm"
              >
                {groups.map((g) => (
                  <option key={g} value={g}>
                    {name(g)}
                  </option>
                ))}
              </select>
            </label>
          )}
          <button
            disabled={start.isPending}
            onClick={() =>
              start.mutate({ version: version === "" ? undefined : version, team_group: groups.length ? group : null })
            }
            className="inline-flex items-center gap-1.5 rounded-lg bg-brand px-3 py-2 text-sm font-medium text-brand-fg hover:bg-brand-strong disabled:opacity-50"
          >
            <Play size={13} /> {start.isPending ? "Starting…" : "Run eval"}
          </button>
        </div>
        <p className="mt-2 text-xs text-surface-600">
          {ready == null ? (
            "Replays up to 20 of the most recent cases people decided."
          ) : ready === 0 ? (
            <span className="text-orange-700">
              No decided cases yet{groups.length ? ` for ${name(group)}` : ""}: decide some cases first, then run an
              eval.
            </span>
          ) : (
            `${ready} decided ${ready === 1 ? "case is" : "cases are"} ready to replay${ready >= (available.data?.limit ?? 20) ? " (the most recent)" : ""}.`
          )}{" "}
          Owners of the capability{groups.length ? " or of the group" : ""} can run one.
        </p>
      </div>
      {start.error && <ErrorState error={start.error} />}

      <section aria-label="Eval runs">
        <h3 className="mb-2 text-sm font-semibold text-surface-900">Results</h3>
        {runs.error && <ErrorState error={runs.error} />}
        {runs.data?.length === 0 && (
          <Empty>
            No evals yet. Run one before approving a draft, or after changing the model or its instructions.
          </Empty>
        )}
        <ul className="space-y-3">
          {(runs.data ?? []).map((r) => (
            <li key={r.run_id} className="rounded-lg border border-surface-200 px-4 py-3">
              <div className="flex flex-wrap items-center gap-2 text-xs">
                <StatusBadge status={r.status} />
                <span className="font-medium text-surface-900">
                  v{r.version}
                  {r.team_group ? ` · ${name(r.team_group)} v${r.group_version}` : ""}
                </span>
                <span className="text-surface-500">
                  by {r.started_by} {formatTime(r.started_at)}
                </span>
              </div>
              {r.status === "running" && (
                <p className="mt-2 text-xs text-surface-500">Replaying past cases… this page updates by itself.</p>
              )}
              <Result r={r} />
              {r.error && <p className="mt-1 text-xs text-red-700">{r.error}</p>}
            </li>
          ))}
        </ul>
      </section>

      <Fold title="How to read a result" summary="when a version is safe to approve">
        <ul className="list-disc space-y-1 pl-5 text-xs text-surface-600">
          <li>
            <b>Agree</b> is the share of past decisions this version would have proposed the same way. Compare it with
            the live version's run.
          </li>
          <li>
            <b>Disagreed</b> needs a look before approving: open “Where it differed from people” to read both sides.
          </li>
          <li>
            <b>Escalated</b> is safe (a person decides) but means less automation than before.
          </li>
          <li>
            <b>Missing</b> or <b>new</b> groups mean the grouping changed, so fewer decisions could be compared.
          </li>
          <li>
            <b>Wording</b> says how close the new explanation is to the words people approved.
          </li>
        </ul>
      </Fold>
    </div>
  );
}
