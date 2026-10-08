// One team group — a team's configuration of a capability (e.g. the CATS vs
// MOTIF rec group): what it sets, its orchestrator step by step (editable by
// its owners where the capability allows), its version history, and YAML for
// those who prefer it. Owners draft; another owner approves.

import { useMemo, useState } from "react";
import { Link, useParams } from "react-router-dom";
import clsx from "clsx";
import { ArrowLeft, Save, Users } from "lucide-react";
import { parse, stringify } from "yaml";

import { currentUser } from "../api/client";
import { useApproveGroup, useDraftGroup, useGroup, type GroupConfig } from "../api/aof";
import FlowDiagram from "../components/capability/FlowDiagram";
import RecurringPanel from "../components/capability/RecurringPanel";
import LearningPanel from "../components/capability/LearningPanel";
import DataContractPanel from "../components/capability/DataContractPanel";
import VersionsPanel from "../components/capability/VersionsPanel";
import OrchestratorEditor from "../components/orchestrator/OrchestratorEditor";
import StatusBadge from "../components/StatusBadge";
import { Card, Empty, ErrorState, Fold, Loading, PageHeader, formatTime } from "../components/ui";

export default function GroupDetail(): JSX.Element {
  const { id = "", group = "" } = useParams();
  const detail = useGroup(id, group);
  const [tab, setTab] = useState<"configure" | "insights" | "data" | "workflow" | "versions">("configure");

  if (detail.isLoading) return <Loading what="group" />;
  if (detail.error) return <ErrorState error={detail.error} />;
  if (!detail.data) return <Empty>Not found.</Empty>;
  const g = detail.data;

  return (
    <div>
      <Link to={`/capabilities/${encodeURIComponent(id)}`} className="inline-flex items-center gap-1 text-xs text-surface-500 hover:text-primary-700">
        <ArrowLeft size={12} /> {id}
      </Link>
      <PageHeader
        title={g.name}
        subtitle={<span>{g.description} <span className="font-mono text-xs text-surface-400">· {g.group} v{g.version}</span></span>}
      />
      <p className="-mt-2 mb-4 flex flex-wrap items-center gap-x-4 gap-y-1 text-sm text-surface-600">
        <span className="inline-flex items-center gap-1.5"><Users size={14} className="text-surface-400" />
          Owned by {[...g.owners.people, g.owners.role].filter(Boolean).join(", ")}{g.owners.four_eyes && " (a second owner approves changes)"}</span>
        <span>Reviewed by {g.review_roles.join(", ")}</span>
        <span>{g.sets.length ? `Changes ${g.sets.length} of the capability's settings` : "Runs on the capability's defaults"}</span>
      </p>

      <div className="mb-4 flex max-w-full overflow-x-auto rounded-lg border border-surface-200 bg-card p-1 sm:inline-flex" role="tablist">
        {(["configure", "insights", "data", "workflow", "versions"] as const).map((t) => (
          <button key={t} role="tab" aria-selected={tab === t} onClick={() => setTab(t)}
            className={clsx("shrink-0 whitespace-nowrap rounded-md px-3 py-1.5 text-sm font-medium",
              tab === t ? "bg-brand-accent text-brand-accent-fg" : "text-surface-600 hover:bg-surface-50")}>
            {({ configure: "Configure", insights: "Insights", data: "Data needed", workflow: "Workflow", versions: "Versions" } as const)[t]}
          </button>
        ))}
      </div>

      {tab === "configure" && (
        <>
          <p className="mb-2 text-xs text-surface-500">
            {g.is_owner ? "Change what this group may set; what the capability decides is shown locked." : "Its owners change it."} Changes go to another owner for approval.
          </p>
          <OrchestratorEditor
            capabilityId={id}
            manifest={g.manifest as unknown as Record<string, unknown>}
            mode={{ kind: "group", config: g.config, configurable: g.configurable }}
            canEdit={g.is_owner}
          />
          <Fold className="mt-4" title="What this group changes" summary={`${g.sets.length} settings`} remember="group-sets">
            <div className="flex flex-wrap gap-1.5">
              {g.sets.length === 0 ? <span className="text-sm text-surface-500">Nothing: it runs on the capability's defaults.</span> :
                g.sets.map((p) => <code key={p} className="rounded bg-surface-100 px-1.5 py-0.5 text-xs text-surface-700">{p}</code>)}
            </div>
            <p className="mt-2 text-xs text-surface-500">Everything else (workflow, gates, write-back, ownership) is the capability's.</p>
          </Fold>
      {g.is_owner && (
        <details className="mt-4 rounded-xl border border-surface-200 bg-card p-4">
          <summary className="cursor-pointer text-sm font-semibold text-surface-800">Advanced: edit this group as YAML</summary>
          <div className="mt-3"><EditGroup capabilityId={id} config={g.config} /></div>
        </details>
      )}
        </>
      )}

      {tab === "insights" && (
        <div className="space-y-4">
          {!!(g.manifest as unknown as { insights?: { recurring?: unknown } }).insights?.recurring && (
            <RecurringPanel capabilityId={id} teamGroup={group} />
          )}
          <LearningPanel capabilityId={id} teamGroup={group} />
        </div>
      )}
      {tab === "data" && <DataContractPanel capabilityId={id} teamGroup={group} />}
      {tab === "workflow" && <Card title="Workflow"><FlowDiagram capabilityId={id} teamGroup={group} /></Card>}
      {tab === "versions" && (
        <div className="grid gap-4 xl:grid-cols-2">
          <Versions capabilityId={id} group={group} versions={g.versions} isOwner={g.is_owner} fourEyes={g.owners.four_eyes} />
          <Card title="What changed between versions">
            <VersionsPanel capabilityId={id} group={group} versions={g.versions} />
          </Card>
        </div>
      )}
    </div>
  );
}

function EditGroup({ capabilityId, config }: { capabilityId: string; config: GroupConfig }) {
  const initial = useMemo(() => stringify(config.set), [config.set]);
  const [text, setText] = useState(initial);
  const [note, setNote] = useState("");
  const [parseError, setParseError] = useState<string | null>(null);
  const draft = useDraftGroup(capabilityId);

  const submit = () => {
    let set: Record<string, unknown>;
    try {
      set = (parse(text) ?? {}) as Record<string, unknown>;
      setParseError(null);
    } catch (e) {
      setParseError(e instanceof Error ? e.message : String(e));
      return;
    }
    draft.mutate({ config: { ...config, set }, note });
  };

  return (
    <div>
      <label className="block text-xs font-medium text-surface-600">
        Settings (YAML) — only what this group changes
        <textarea
          value={text}
          onChange={(e) => setText(e.target.value)}
          rows={14}
          spellCheck={false}
          className="mt-1 block w-full rounded-lg border border-surface-300 bg-code-bg px-3 py-2 font-mono text-xs text-code-fg focus:outline-none"
        />
      </label>
      <div className="mt-2 flex flex-wrap items-end gap-2">
        <label className="flex-1 text-xs font-medium text-surface-600">
          Note for the approver
          <input value={note} onChange={(e) => setNote(e.target.value)} className="mt-1 block w-full rounded-lg border border-surface-300 px-3 py-1.5 text-sm font-normal" />
        </label>
        <button
          onClick={submit}
          disabled={draft.isPending || text === initial}
          className="inline-flex items-center gap-2 rounded-lg bg-brand px-4 py-2 text-sm font-medium text-brand-fg hover:bg-brand-strong disabled:opacity-50"
        >
          <Save size={14} /> Submit for approval
        </button>
      </div>
      {parseError && <div className="mt-2"><ErrorState error={new Error(`Not valid YAML: ${parseError}`)} /></div>}
      {draft.error && <div className="mt-2"><ErrorState error={draft.error} /></div>}
      {draft.data && <p className="mt-2 text-sm text-green-700">Version {draft.data.version} drafted. Another owner approves it under Versions.</p>}
    </div>
  );
}

function Versions({ capabilityId, group, versions, isOwner, fourEyes }: {
  capabilityId: string;
  group: string;
  versions: { version: number; status: string; note: string; drafted_by: string; drafted_at: string; decided_by: string | null }[];
  isOwner: boolean;
  fourEyes: boolean;
}) {
  const approve = useApproveGroup(capabilityId, group);
  const me = currentUser(); // UX only: the server enforces four-eyes
  return (
    <Card title="Versions">
      <ul className="divide-y divide-surface-100 text-sm">
        {versions.map((v) => (
          <li key={v.version} className="flex flex-wrap items-center gap-3 py-2">
            <span className="font-mono text-xs">v{v.version}</span>
            <StatusBadge status={v.status} />
            <span className="text-surface-600">{v.note || "—"}</span>
            <span className="ml-auto text-xs text-surface-500">
              {v.drafted_by} {formatTime(v.drafted_at)}{v.decided_by && <> · approved by {v.decided_by}</>}
            </span>
            {v.status === "draft" && isOwner && (!fourEyes || v.drafted_by !== me) && (
              <button
                onClick={() => approve.mutate(v.version)}
                disabled={approve.isPending}
                className="rounded-lg bg-brand-accent px-3 py-1 text-xs font-medium text-brand-accent-fg hover:bg-brand-accent-strong disabled:opacity-50"
              >
                Approve
              </button>
            )}
          </li>
        ))}
      </ul>
      {approve.error && <ErrorState error={approve.error} />}
    </Card>
  );
}
