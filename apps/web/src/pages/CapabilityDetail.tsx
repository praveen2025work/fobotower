import { useState } from "react";
import { Link, useNavigate, useParams } from "react-router-dom";
import clsx from "clsx";
import { Play } from "lucide-react";

import { useCapability, useCases, useOpenCase, type Manifest } from "../api/helix";
import StatusBadge from "../components/StatusBadge";
import { Card, Empty, ErrorState, Loading, PageHeader, WorkflowStepper, formatTime } from "../components/ui";

type Tab = "cases" | "definition" | "versions";

export default function CapabilityDetail(): JSX.Element {
  const { id = "" } = useParams();
  const cap = useCapability(id);
  const [tab, setTab] = useState<Tab>("cases");

  if (cap.isLoading) return <Loading what="capability" />;
  if (cap.error) return <ErrorState error={cap.error} />;
  if (!cap.data) return <Empty>Not found.</Empty>;
  const m = cap.data.manifest;

  return (
    <div>
      <PageHeader
        title={m.name}
        subtitle={<span>{m.description} <span className="font-mono text-xs text-surface-400">· {m.id} v{cap.data.version}</span></span>}
      />
      <div className="mb-4 rounded-xl border border-surface-200 bg-white p-4">
        <WorkflowStepper steps={m.steps} pauseBefore={m.pause_before} />
      </div>
      <div className="mb-4 inline-flex rounded-lg border border-surface-200 bg-white p-1" role="tablist">
        {(["cases", "definition", "versions"] as Tab[]).map((t) => (
          <button
            key={t}
            role="tab"
            aria-selected={tab === t}
            onClick={() => setTab(t)}
            className={clsx("rounded-md px-3 py-1.5 text-sm font-medium capitalize", tab === t ? "bg-accent-500 text-white" : "text-surface-600 hover:bg-surface-50")}
          >
            {t === "cases" ? `${m.case.label}s` : t}
          </button>
        ))}
      </div>
      {tab === "cases" && <CasesTab id={id} manifest={m} />}
      {tab === "definition" && <DefinitionTab manifest={m} />}
      {tab === "versions" && (
        <Card title="Versions" aside={<span className="text-xs text-surface-500">An owner drafts; a different owner approves.</span>}>
          <ul className="divide-y divide-surface-100 text-sm">
            {cap.data.versions.map((v) => (
              <li key={v.version} className="flex flex-wrap items-center gap-3 py-2">
                <span className="font-mono text-xs">v{v.version}</span>
                <StatusBadge status={v.status} />
                <span className="text-surface-600">{v.note || "—"}</span>
                <span className="ml-auto text-xs text-surface-500">
                  drafted by {v.drafted_by} {formatTime(v.drafted_at)}
                  {v.decided_by && <> · approved by {v.decided_by}</>}
                </span>
              </li>
            ))}
          </ul>
        </Card>
      )}
    </div>
  );
}

function CasesTab({ id, manifest }: { id: string; manifest: Manifest }) {
  const cases = useCases(id);
  const open = useOpenCase(id);
  const navigate = useNavigate();
  const [values, setValues] = useState<Record<string, string>>(() => Object.fromEntries(manifest.case.key.map((k) => [k, ""])));

  const submit = (e: React.FormEvent) => {
    e.preventDefault();
    open.mutate(values, { onSuccess: (d) => navigate(`/cases/${encodeURIComponent(d.case_id)}`) });
  };

  return (
    <div className="grid gap-4 xl:grid-cols-3">
      <Card title={`Open a ${manifest.case.label.toLowerCase()}`}>
        <form onSubmit={submit} className="space-y-3">
          {manifest.case.key.map((k) => (
            <label key={k} className="block text-xs font-medium text-surface-600">
              {k}
              <input
                required
                value={values[k]}
                onChange={(e) => setValues((v) => ({ ...v, [k]: e.target.value }))}
                className="mt-1 block w-full rounded-lg border border-surface-300 px-3 py-1.5 text-sm font-normal text-surface-900 focus:border-primary-400 focus:outline-none"
              />
            </label>
          ))}
          <button
            type="submit"
            disabled={open.isPending}
            className="inline-flex items-center gap-2 rounded-lg bg-primary-700 px-4 py-2 text-sm font-medium text-white hover:bg-primary-800 disabled:opacity-50"
          >
            <Play size={14} /> {open.isPending ? "Running…" : "Open and run"}
          </button>
          {open.error && <ErrorState error={open.error} />}
        </form>
      </Card>
      <Card title={`${manifest.case.label}s`} className="xl:col-span-2">
        {cases.isLoading && <Loading what="cases" />}
        {cases.error && <ErrorState error={cases.error} />}
        {cases.data?.length === 0 && <Empty>No {manifest.case.label.toLowerCase()}s yet.</Empty>}
        <ul className="divide-y divide-surface-100">
          {cases.data?.map((c) => (
            <li key={c.case_id}>
              <Link to={`/cases/${encodeURIComponent(c.case_id)}`} className="flex items-center justify-between gap-2 px-1 py-2.5 text-sm hover:bg-surface-50">
                <span className="font-medium text-surface-800">{c.subject}</span>
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

function Field({ label, children }: { label: string; children: React.ReactNode }) {
  return (
    <div className="grid grid-cols-3 gap-2 py-1.5 text-sm">
      <dt className="text-surface-500">{label}</dt>
      <dd className="col-span-2 text-surface-800">{children}</dd>
    </div>
  );
}

function Tools({ names }: { names: string[] }) {
  return (
    <span className="flex flex-wrap gap-1">
      {names.length ? names.map((t) => <code key={t} className="rounded bg-surface-100 px-1.5 py-0.5 text-xs">{t}</code>) : "—"}
    </span>
  );
}

function DefinitionTab({ manifest: m }: { manifest: Manifest }) {
  return (
    <div className="grid gap-4 xl:grid-cols-2">
      <Card title="Case and items">
        <dl className="divide-y divide-surface-100">
          <Field label="Case">{m.case.label} per {m.case.key.join(" × ")} (opens on {m.case.opens_on})</Field>
          <Field label="Data scope">{Object.entries(m.case.scopes).map(([f, s]) => `${f} → ${s}`).join(", ") || "—"}</Field>
          <Field label="Items from">{m.items.load ? <Tools names={[m.items.load.tool]} /> : m.match ? <Tools names={[m.match.left.tool, m.match.right.tool]} /> : "—"}</Field>
          <Field label="In scope when"><code className="text-xs">{m.items.in_scope ?? "always"}</code></Field>
          <Field label="Grouped by">{m.group_by.join(", ") || "one group"}</Field>
        </dl>
      </Card>
      <Card title="Reasoning">
        <dl className="divide-y divide-surface-100">
          <Field label="Rules first">{m.rules.length ? m.rules.map((r) => <div key={r.id}><code className="text-xs">{r.when}</code> → {r.then.status}</div>) : "none"}</Field>
          <Field label="Then">{m.reasoning.reasoner === "llm" ? "the model, with these tools" : "people (no model)"}</Field>
          <Field label="Model tools"><Tools names={m.reasoning.tools} /></Field>
          <Field label="Instructions"><p className="whitespace-pre-wrap text-xs text-surface-600">{m.reasoning.skill || "—"}</p></Field>
        </dl>
      </Card>
      <Card title="People and governance">
        <dl className="divide-y divide-surface-100">
          <Field label="Reviewers">{m.review.roles.join(", ")}</Field>
          <Field label="Owners">{[...m.owners.people, m.owners.role].filter(Boolean).join(", ")}{m.owners.four_eyes && " · four-eyes"}</Field>
          <Field label="Write-back">{m.publish ? <><Tools names={[m.publish.tool]} /> released by {m.publish.approver_roles.join(", ")}</> : "none"}</Field>
          <Field label="Policy">{Object.entries(m.policy).map(([k, v]) => `${k} = ${String(v.value)}${v.unit ? ` ${v.unit}` : ""}`).join(", ") || "—"}</Field>
        </dl>
      </Card>
    </div>
  );
}
