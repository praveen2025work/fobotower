import { Link } from "react-router-dom";
import { Layers, ShieldCheck } from "lucide-react";

import { useCapabilities } from "../api/helix";
import { Empty, ErrorState, Loading, PageHeader, WorkflowStepper } from "../components/ui";

/** The catalogue: every capability the user's roles allow — each one configuration only. */
export default function Capabilities(): JSX.Element {
  const caps = useCapabilities();
  return (
    <div>
      <PageHeader title="Capabilities" subtitle="Each capability is a versioned manifest over onboarded connectors — no code per use case." />
      {caps.isLoading && <Loading what="capabilities" />}
      {caps.error && <ErrorState error={caps.error} />}
      {caps.data?.length === 0 && <Empty>No capabilities for your roles.</Empty>}
      <div className="grid gap-4 lg:grid-cols-2">
        {caps.data?.map((c) => (
          <Link
            key={c.id}
            to={`/capabilities/${encodeURIComponent(c.id)}`}
            className="group rounded-xl border border-surface-200 bg-card p-5 transition-colors hover:border-primary-300"
          >
            <div className="flex items-start justify-between gap-3">
              <div className="flex items-center gap-2.5">
                <div className="flex h-9 w-9 items-center justify-center rounded-lg bg-accent-50 text-accent-600">
                  <Layers size={18} />
                </div>
                <div>
                  <h2 className="font-semibold text-surface-900 group-hover:text-primary-700">{c.name}</h2>
                  <p className="font-mono text-[11px] text-surface-400">{c.id} · v{c.version}</p>
                </div>
              </div>
              <div className="flex gap-1.5 text-[10px]">
                {c.is_owner && <span className="rounded bg-primary-50 px-1.5 py-0.5 font-medium text-primary-700">Owner</span>}
                {c.can_decide && (
                  <span className="inline-flex items-center gap-1 rounded bg-accent-50 px-1.5 py-0.5 font-medium text-accent-700">
                    <ShieldCheck size={10} /> Reviewer
                  </span>
                )}
              </div>
            </div>
            {c.description && <p className="mt-3 text-sm text-surface-600">{c.description}</p>}
            <p className="mt-3 text-xs text-surface-500">
              One <span className="font-medium text-surface-700">{c.case_label}</span> per {c.case_key.join(" × ")} · items are{" "}
              <span className="font-medium text-surface-700">{c.item_label.toLowerCase()}s</span>
            </p>
            {c.groups.length > 0 && (
              <div className="mt-3 flex flex-wrap items-center gap-1.5 text-xs text-surface-500">
                Configured by
                {c.groups.map((g) => (
                  <span key={g.group} className="rounded bg-primary-50 px-1.5 py-0.5 font-medium text-primary-700">{g.name}</span>
                ))}
              </div>
            )}
            <div className="mt-3">
              <WorkflowStepper steps={c.steps} />
            </div>
          </Link>
        ))}
      </div>
    </div>
  );
}
