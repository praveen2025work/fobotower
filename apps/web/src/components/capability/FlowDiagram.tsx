// A capability's workflow as a diagram, drawn from the manifest (GET /flow):
// each step a box — gates outlined, pauses for people marked — with the tools
// it uses and the people who decide. Never drawn by hand, so never stale.

import clsx from "clsx";
import { Pause, ShieldCheck, Users, Wrench } from "lucide-react";

import { useFlow } from "../../api/aof";
import { ErrorState, Loading } from "../ui";

export default function FlowDiagram({ capabilityId, teamGroup }: { capabilityId: string; teamGroup?: string | null }) {
  const flow = useFlow(capabilityId, teamGroup);
  if (flow.isLoading) return <Loading what="workflow" />;
  if (flow.error) return <ErrorState error={flow.error} />;
  const f = flow.data!;
  return (
    <div aria-label="Workflow diagram">
      <p className="mb-3 text-xs text-surface-500">
        Opens {f.opens.on === "schedule" ? <>on schedule <code>{f.opens.schedule}</code></> : f.opens.on}
        {f.opens.events && " · also on events from other systems"}
      </p>
      <ol className="flex flex-wrap items-stretch gap-2">
        {f.nodes.map((n, i) => (
          <li key={n.id} className="flex items-stretch gap-2">
            <div
              className={clsx(
                "w-44 rounded-lg border bg-card p-2.5 text-xs",
                n.gate ? "border-2 border-primary-600" : "border-surface-200",
              )}
              data-testid={`flow-${n.id}`}
            >
              <div className="flex items-center gap-1.5">
                {n.pause && <Pause size={11} className="text-primary-700" aria-label="pauses for people" />}
                {n.gate && <ShieldCheck size={11} className="text-primary-600" aria-label="gate" />}
                <span className="font-semibold text-surface-900">{n.id}</span>
              </div>
              {n.tools.map((t) => (
                <p key={t} className="mt-1 flex items-center gap-1 font-mono text-[10px] text-surface-600"><Wrench size={9} /> {t}</p>
              ))}
              {n.notes.map((t) => <p key={t} className="mt-1 text-[10px] text-surface-500">{t}</p>)}
              {n.people.length > 0 && (
                <p className="mt-1 flex items-center gap-1 text-[10px] font-medium text-primary-700"><Users size={9} /> {n.people.join(", ")}</p>
              )}
            </div>
            {i < f.nodes.length - 1 && <span className="self-center text-surface-300" aria-hidden>→</span>}
          </li>
        ))}
      </ol>
      <p className="mt-3 text-[11px] text-surface-500">Bold outline: a gate that can never be removed. Pause: the run waits for a person.</p>
    </div>
  );
}
