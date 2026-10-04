// One team group — a team's configuration of a capability (e.g. the CATS vs
// MOTIF rec group): what it sets, the configuration its cases run on, its
// version history, and editing it (owners draft; another owner approves).

import { useMemo, useState } from "react";
import { Link, useParams } from "react-router-dom";
import { ArrowLeft, Save, Users } from "lucide-react";
import { parse, stringify } from "yaml";

import { currentUser } from "../api/client";
import { useApproveGroup, useDraftGroup, useGroup, type GroupConfig } from "../api/helix";
import FlowDiagram from "../components/capability/FlowDiagram";
import InstructionsEditor from "../components/capability/InstructionsEditor";
import VersionsPanel from "../components/capability/VersionsPanel";
import StatusBadge from "../components/StatusBadge";
import { Card, Empty, ErrorState, Loading, PageHeader, formatTime } from "../components/ui";
import { ManifestDefinition } from "./CapabilityDetail";

export default function GroupDetail(): JSX.Element {
  const { id = "", group = "" } = useParams();
  const detail = useGroup(id, group);

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
      <div className="mb-4 grid gap-4 lg:grid-cols-3">
        <Card title={<span className="flex items-center gap-2"><Users size={14} /> People</span>}>
          <dl className="space-y-1.5 text-sm">
            <div><dt className="text-xs text-surface-500">Owners (change this group)</dt><dd>{[...g.owners.people, g.owners.role].filter(Boolean).join(", ")}{g.owners.four_eyes && " · four-eyes"}</dd></div>
            <div><dt className="text-xs text-surface-500">Reviewers (sign off its cases)</dt><dd>{g.review_roles.join(", ")}</dd></div>
          </dl>
        </Card>
        <Card title="What this group sets" className="lg:col-span-2">
          <div className="flex flex-wrap gap-1.5">
            {g.sets.length === 0 ? <span className="text-sm text-surface-500">Nothing — it runs on the capability's defaults.</span> :
              g.sets.map((p) => <code key={p} className="rounded bg-accent-50 px-1.5 py-0.5 text-xs text-accent-700">{p}</code>)}
          </div>
          <p className="mt-3 text-xs text-surface-500">
            Everything else — workflow, gates, write-back, ownership — is the capability's. Allowed here: {g.configurable.join(", ")}.
          </p>
        </Card>
      </div>

      <h2 className="mb-2 text-sm font-semibold text-surface-800">Configuration its cases run on</h2>
      <ManifestDefinition manifest={g.manifest} />

      <div className="mt-4">
        <Card title="Workflow"><FlowDiagram capabilityId={id} teamGroup={group} /></Card>
      </div>

      <div className="mt-4 grid gap-4 xl:grid-cols-2">
        {g.is_owner && <EditGroup capabilityId={id} config={g.config} />}
        <Versions capabilityId={id} group={group} versions={g.versions} isOwner={g.is_owner} fourEyes={g.owners.four_eyes} />
      </div>

      <div className="mt-4 grid gap-4 xl:grid-cols-2">
        {g.is_owner && (
          <Card title="This team's model instructions">
            <InstructionsEditor capabilityId={id} teamGroup={group} current={g.manifest.reasoning.skill} />
          </Card>
        )}
        <Card title="What changed between versions">
          <VersionsPanel capabilityId={id} group={group} versions={g.versions} />
        </Card>
      </div>
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
    <Card title="Change this group">
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
      {draft.data && <p className="mt-2 text-sm text-green-700">Version {draft.data.version} drafted. Another owner approves it below.</p>}
    </Card>
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
