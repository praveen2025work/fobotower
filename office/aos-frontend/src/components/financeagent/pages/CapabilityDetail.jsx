// Generated from apps/web/src/pages/CapabilityDetail.tsx by apps/web/office/convert.mjs. Office changes to this file are
// kept by aof_sync.py on the next update; see docs/agent-one-finance/office/conversion-guide.md.
import { useState } from "react";
import { Link, useNavigate, useParams } from "../office/router";
import clsx from "clsx";
import { Play, Plus } from "lucide-react";

import { Users } from "lucide-react";

import { useCapabilities, useCapability, useCases, useGroups, useOpenCase } from "../api/aof";
import EvalsPanel from "../components/capability/EvalsPanel";
import RecurringPanel from "../components/capability/RecurringPanel";
import LearningPanel from "../components/capability/LearningPanel";
import DataContractPanel from "../components/capability/DataContractPanel";
import FlowDiagram from "../components/capability/FlowDiagram";
import VersionsPanel from "../components/capability/VersionsPanel";
import OrchestratorEditor from "../components/orchestrator/OrchestratorEditor";
import StatusBadge from "../components/StatusBadge";
import { Card, Empty, ErrorState, Fold, Loading, PageHeader, formatTime } from "../components/ui";

export default function CapabilityDetail() {
  const { id = "" } = useParams();
  const cap = useCapability(id);
  const caps = useCapabilities();
  const groups = useGroups(id);
  const hasGroups = (groups.data?.length ?? 0) > 0;
  const [chosen, setTab] = useState(null);
  // What most visitors come for: the cases. Owners go to Groups or Configure when they need to.
  const tab = chosen ?? "cases";

  if (cap.isLoading) return <Loading what="capability" />;
  if (cap.error) return <ErrorState error={cap.error} />;
  if (!cap.data) return <Empty>Not found.</Empty>;
  const m = cap.data.manifest;
  const isOwner = !!caps.data?.find((x) => x.id === id)?.is_owner;
  const hasRecurring = !!m.insights?.recurring;

  return (
    <div>
      <PageHeader
        title={m.name}
        subtitle={
          <span>
            {m.description}{" "}
            <span className="font-mono text-xs text-surface-400">
              · {m.id} v{cap.data.version}
            </span>
          </span>
        }
      />
      <p className="-mt-2 mb-4 text-sm text-surface-500">
        {m.steps.length} steps
        {m.pause_before.length > 0 && <> · stops for a person before {m.pause_before.join(" and ")}</>} ·{" "}
        <button type="button" onClick={() => setTab("flow")} className="font-medium text-primary-700 hover:underline">
          see how a case runs
        </button>
      </p>
      <div
        className="mb-4 flex max-w-full overflow-x-auto rounded-lg border border-surface-200 bg-card p-1 sm:inline-flex"
        role="tablist"
      >
        {["cases", ...(hasGroups ? ["groups"] : []), "configure", "flow", "evals", "versions"].map((t) => (
          <button
            key={t}
            role="tab"
            aria-selected={tab === t}
            onClick={() => setTab(t)}
            className={clsx(
              "shrink-0 whitespace-nowrap rounded-md px-3 py-1.5 text-sm font-medium capitalize",
              tab === t ? "bg-brand-accent text-brand-accent-fg" : "text-surface-600 hover:bg-surface-50",
            )}
          >
            {t === "cases" ? "Cases" : t === "flow" ? <span className="normal-case">How it runs</span> : t}
          </button>
        ))}
      </div>
      {tab === "groups" && <GroupsTab id={id} groups={groups.data ?? []} configurable={m.configurable} />}
      {tab === "cases" && <CasesTab id={id} manifest={m} groups={groups.data ?? []} />}
      {tab === "cases" && (
        <Fold
          className="mt-4"
          remember="capability-insights"
          title="Insights"
          summary="what keeps coming back, and what could become a rule"
        >
          <div className="space-y-4">
            {(hasRecurring || (groups.data ?? []).length > 0) && <RecurringPanel capabilityId={id} />}
            <LearningPanel capabilityId={id} />
          </div>
        </Fold>
      )}
      {tab === "configure" && (
        <>
          <p className="mb-2 text-sm text-surface-500">
            Pick a step on the left to change it.
            {isOwner ? " Changes become a draft that another owner approves." : " Its owners change it."}
            {hasGroups && " Team groups may override what the owners allow."}
          </p>
          <OrchestratorEditor capabilityId={id} manifest={m} mode={{ kind: "capability" }} canEdit={isOwner} />
          <Fold
            className="mt-4"
            remember="data-contract"
            title="Data and parameters"
            summary="the fields each check reads, and thresholds to confirm"
          >
            <DataContractPanel capabilityId={id} />
          </Fold>
        </>
      )}
      {tab === "flow" && (
        <Card title="How a case runs">
          <FlowDiagram capabilityId={id} />
        </Card>
      )}
      {tab === "evals" && (
        <Card title="Evals: try a version on past decisions">
          <EvalsPanel
            capabilityId={id}
            versions={cap.data.versions.map((v) => v.version)}
            groups={(groups.data ?? []).map((g) => g.group)}
            statuses={Object.fromEntries(cap.data.versions.map((v) => [v.version, v.status]))}
            groupNames={Object.fromEntries((groups.data ?? []).map((g) => [g.group, g.name]))}
          />
        </Card>
      )}
      {tab === "versions" && (
        <div className="space-y-4">
          <Card
            title="Versions"
            aside={<span className="text-xs text-surface-500">An owner drafts; a different owner approves.</span>}
          >
            <VersionsPanel capabilityId={id} versions={cap.data.versions} />
          </Card>
        </div>
      )}
    </div>
  );
}

function GroupsTab({ id, groups, configurable }) {
  return (
    <div>
      <p className="mb-3 text-sm text-surface-500">
        Each team runs this capability with its own settings, within the {configurable.length} the capability allows.
      </p>
      <div className="grid gap-4 lg:grid-cols-2">
        {groups.map((g) => (
          <Link
            key={g.group}
            to={`/capabilities/${encodeURIComponent(id)}/groups/${encodeURIComponent(g.group)}`}
            className="group rounded-xl border border-surface-200 bg-card p-5 transition-colors hover:border-primary-300"
          >
            <div className="flex items-start justify-between gap-2">
              <div className="flex items-center gap-2.5">
                <div className="flex h-9 w-9 items-center justify-center rounded-lg bg-primary-50 text-primary-600">
                  <Users size={17} />
                </div>
                <div>
                  <h2 className="font-semibold text-surface-900 group-hover:text-primary-700">{g.name}</h2>
                  <p className="font-mono text-[11px] text-surface-400">
                    {g.group} · v{g.version}
                  </p>
                </div>
              </div>
              <div className="flex gap-1.5 text-[10px]">
                {g.is_owner && (
                  <span className="rounded bg-primary-50 px-1.5 py-0.5 font-medium text-primary-700">Owner</span>
                )}
                {g.can_decide && (
                  <span className="rounded bg-accent-50 px-1.5 py-0.5 font-medium text-accent-700">Reviewer</span>
                )}
              </div>
            </div>
            {g.description && <p className="mt-3 text-sm text-surface-600">{g.description}</p>}
            <p className="mt-3 text-xs text-surface-500">
              {g.case_label} per {g.case_key.join(" × ")} · reviewed by {g.review_roles.join(", ")}
            </p>
            <p className="mt-1 text-xs text-surface-400">
              {g.sets.length === 0
                ? "Uses the capability's defaults"
                : `Sets ${g.sets.length} of the capability's settings`}
            </p>
          </Link>
        ))}
      </div>
    </div>
  );
}

function CasesTab({ id, manifest, groups }) {
  const openable = groups.filter((g) => g.can_open);
  const [group, setGroup] = useState(openable[0]?.group ?? "");
  const [filter, setFilter] = useState("");
  const cases = useCases(id, filter || undefined);
  const open = useOpenCase(id);
  const navigate = useNavigate();
  const chosen = groups.find((g) => g.group === group);
  const keyFields = chosen ? chosen.case_key : manifest.case.key;
  const label = chosen ? chosen.case_label : manifest.case.label;
  const [values, setValues] = useState({});
  const names = Object.fromEntries(groups.map((g) => [g.group, g.name]));
  const [opening, setOpening] = useState(false);

  const submit = (e) => {
    e.preventDefault();
    const caseKey = Object.fromEntries(keyFields.map((k) => [k, values[k] ?? ""]));
    open.mutate(
      { caseKey, teamGroup: groups.length ? group : null },
      {
        onSuccess: (d) => navigate(`/cases/${encodeURIComponent(d.case_id)}`),
      },
    );
  };

  const canOpen = !(groups.length > 0 && openable.length === 0);
  return (
    <div>
      <Card
        title="Cases"
        aside={
          <div className="flex items-center gap-2">
            {groups.length > 0 && (
              <select
                aria-label="Filter by group"
                value={filter}
                onChange={(e) => setFilter(e.target.value)}
                className="rounded-lg border border-surface-300 bg-card px-2 py-1 text-xs"
              >
                <option value="">All groups</option>
                {groups.map((g) => (
                  <option key={g.group} value={g.group}>
                    {g.name}
                  </option>
                ))}
              </select>
            )}
            {canOpen && (
              <button
                type="button"
                onClick={() => setOpening(!opening)}
                aria-expanded={opening}
                className="inline-flex items-center gap-1 rounded-lg border border-surface-300 px-2.5 py-1 text-xs font-medium text-surface-700 hover:bg-surface-50"
              >
                <Plus size={12} /> Open a {label.toLowerCase()}
              </button>
            )}
          </div>
        }
      >
        {opening && (
          <div className="mb-4 rounded-lg border border-surface-200 bg-surface-50 p-3">
            <p className="mb-2 text-xs text-surface-500">
              Cases usually open by themselves (an event or a schedule). Open one by hand here.
            </p>
            {groups.length > 0 && openable.length === 0 ? (
              <Empty>None of this capability's groups lets you open cases.</Empty>
            ) : (
              <form
                onSubmit={submit}
                className="grid gap-3 sm:grid-cols-[repeat(auto-fit,minmax(10rem,1fr))] sm:items-end"
              >
                {groups.length > 0 && (
                  <label className="block text-xs font-medium text-surface-600">
                    Group
                    <select
                      value={group}
                      onChange={(e) => setGroup(e.target.value)}
                      className="mt-1 block w-full rounded-lg border border-surface-300 bg-card px-3 py-1.5 text-sm font-normal"
                    >
                      {openable.map((g) => (
                        <option key={g.group} value={g.group}>
                          {g.name}
                        </option>
                      ))}
                    </select>
                  </label>
                )}
                {keyFields.map((k) => (
                  <label key={k} className="block text-xs font-medium text-surface-600">
                    {k}
                    <input
                      required
                      value={values[k] ?? ""}
                      onChange={(e) => setValues((v) => ({ ...v, [k]: e.target.value }))}
                      className="mt-1 block w-full rounded-lg border border-surface-300 px-3 py-1.5 text-sm font-normal text-surface-900 focus:border-primary-400 focus:outline-none"
                    />
                  </label>
                ))}
                <button
                  type="submit"
                  disabled={open.isPending}
                  className="inline-flex items-center gap-2 rounded-lg bg-brand px-4 py-2 text-sm font-medium text-brand-fg hover:bg-brand-strong disabled:opacity-50"
                >
                  <Play size={14} /> {open.isPending ? "Running…" : "Open and run"}
                </button>
                {open.error && <ErrorState error={open.error} />}
              </form>
            )}
          </div>
        )}
        {cases.isLoading && <Loading what="cases" />}
        {cases.error && <ErrorState error={cases.error} />}
        {cases.data?.length === 0 && <Empty>No cases yet.</Empty>}
        <ul className="divide-y divide-surface-100">
          {cases.data?.map((c) => (
            <li key={c.case_id}>
              <Link
                to={`/cases/${encodeURIComponent(c.case_id)}`}
                className="flex items-center justify-between gap-2 px-1 py-2.5 text-sm hover:bg-surface-50"
              >
                <span>
                  <span className="font-medium text-surface-800">{c.subject}</span>
                  {c.team_group && (
                    <span className="ml-2 rounded bg-primary-50 px-1.5 py-0.5 text-[10px] font-medium text-primary-700">
                      {names[c.team_group] ?? c.team_group}
                    </span>
                  )}
                </span>
                <span className="flex items-center gap-3 text-xs text-surface-500">
                  {formatTime(c.opened_at)} · {c.opened_by}
                  <StatusBadge status={c.status} />
                </span>
              </Link>
            </li>
          ))}
        </ul>
      </Card>
    </div>
  );
}
