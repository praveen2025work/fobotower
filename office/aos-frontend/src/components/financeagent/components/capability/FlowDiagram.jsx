// Generated from apps/web/src/components/capability/FlowDiagram.tsx by apps/web/office/convert.mjs. Office changes to this file are
// kept by aof_sync.py on the next update; see docs/agent-one-finance/office/conversion-guide.md.
// A capability's workflow as a short story, drawn from the manifest (GET /flow):
// how a case opens, then phases in order — get the data, find the cause,
// propose, check, a person decides, record — each saying who acts, with its
// steps in plain words, the systems they read and where the run stops for a
// person. Derived from the configuration, so never stale.

import clsx from "clsx";
import {
  Bot,
  CalendarClock,
  Cog,
  Database,
  Hand,
  ListChecks,
  Play,
  ShieldCheck,
  User,
  Users,
  Wrench,
} from "lucide-react";

import { useFlow } from "../../api/aof";
import { DATA_TYPES } from "../orchestrator/PrepareSteps";
import { ErrorState, Loading } from "../ui";

const PHASES = {
  gather: {
    title: "Get the data",
    who: "System",
    icon: Database,
    says: "Reads the items and what is needed beside them, through the approved connectors.",
  },
  explain: {
    title: "Find the cause",
    who: "Rules, no model",
    icon: Cog,
    says: "Checks and algorithms explain what they can, and mark each item with what they found.",
  },
  propose: {
    title: "Propose a decision",
    who: "Rules, then the model",
    icon: Bot,
    says: "Items are grouped for one decision each; rules settle what they can, the model investigates the rest.",
  },
  check: {
    title: "Check every figure",
    who: "Platform (always on)",
    icon: ShieldCheck,
    says: "Every figure in a proposal must come from the data read; if not, it goes to a person.",
  },
  people: {
    title: "A person decides",
    who: "People",
    icon: User,
    says: "Nothing is settled until someone with the right role approves or rejects it, in their own words.",
  },
  after: {
    title: "Record and act",
    who: "System, after approval",
    icon: ListChecks,
    says: "Decisions are kept for audit and learning; only approved outcomes are written back.",
  },
};

/** The core steps, in plain words. Configurable steps take their name from the step catalogue. */
const CORE = {
  load: { name: "Read the items", phase: "gather" },
  match: {
    name: "Match the two systems",
    phase: "gather",
    says: "Matches by key and tolerance; what does not match becomes an item.",
  },
  enrich: { name: "Add more data to each item", phase: "gather" },
  resolve: { name: "Look up owners", phase: "explain", says: "Follows reference data to the owning team or desk." },
  classify: {
    name: "Run the playbook",
    phase: "explain",
    says: "Cause checks and validation tests give each item a category and a verdict.",
  },
  group: { name: "Group for one decision", phase: "propose" },
  reason: {
    name: "Rules, then the model",
    phase: "propose",
    says: "Rules settle what they can; the model investigates the rest with only the tools allowed.",
  },
  agent: {
    name: "Skill session",
    phase: "propose",
    says: "One model session follows the skill, reading data only through the allowed tools.",
  },
  draft: { name: "Draft the summary", phase: "propose" },
  validate: { name: "Check every figure", phase: "check" },
  review: { name: "People decide", phase: "people" },
  record: { name: "Record the decisions", phase: "after", says: "Kept for audit, and so later runs learn from them." },
  publish: {
    name: "Write back",
    phase: "after",
    says: "Writes approved results to the target system after a second person releases them.",
  },
};

const TYPE = Object.fromEntries(DATA_TYPES.map((t) => [t.type, t]));

function phaseOf(n, afterRecord) {
  if (CORE[n.id]) return CORE[n.id].phase;
  if (afterRecord) return "after";
  const t = TYPE[n.type ?? ""];
  if (!t) return "explain";
  if (t.type === "attest") return "people";
  if (["propose_entries", "compose"].includes(t.type)) return "propose";
  if (["post", "report", "outreach"].includes(t.type)) return "after";
  if (["Data", "Acquisition"].includes(t.family) || ["timeline", "link"].includes(t.type)) return "gather";
  return "explain";
}

const humanize = (id) => id.replace(/[_-]+/g, " ").replace(/^\w/, (c) => c.toUpperCase());

function nameOf(n) {
  const t = TYPE[n.type ?? ""];
  const name = n.label || CORE[n.id]?.name || humanize(n.id);
  const kind = t && t.label.toLowerCase() !== name.toLowerCase() ? t.label : null;
  // a step the team named says what it is; the catalogue's generic sentence would only repeat
  return { name, kind, says: CORE[n.id]?.says ?? (n.label ? null : (t?.says ?? null)) };
}

/** Consecutive steps of the same phase form one block, so the order shown is the order run. */
function blocks(nodes) {
  const out = [];
  let afterRecord = false;
  for (const n of nodes) {
    const p = phaseOf(n, afterRecord);
    if (n.id === "record") afterRecord = true;
    if (out.length && out[out.length - 1].phase === p) out[out.length - 1].nodes.push(n);
    else out.push({ phase: p, nodes: [n] });
  }
  return out;
}

function opensText(o) {
  if (o.on === "schedule")
    return (
      <>
        On a schedule: <code className="font-mono text-xs">{o.schedule}</code>
      </>
    );
  if (o.on === "event") return <>When another system sends an event</>;
  return <>When someone opens it</>;
}

export default function FlowDiagram({ capabilityId, teamGroup }) {
  const flow = useFlow(capabilityId, teamGroup);
  if (flow.isLoading) return <Loading what="workflow" />;
  if (flow.error) return <ErrorState error={flow.error} />;
  const f = flow.data;
  const parts = blocks(f.nodes);
  const tollgates = f.nodes.filter((n) => n.pause && n.id !== "review").length;

  return (
    <div aria-label="Workflow diagram" className="space-y-4">
      {/* At a glance: the phases in order, with how many steps each. */}
      <ol aria-label="At a glance" className="flex flex-wrap items-center gap-1.5 text-xs">
        <li className="inline-flex items-center gap-1 rounded-full bg-surface-100 px-2.5 py-1 text-surface-700">
          <Play size={11} /> Opens
        </li>
        {parts.map((b, i) => {
          const P = PHASES[b.phase];
          const person = b.phase === "people";
          return (
            <li key={i} className="inline-flex items-center gap-1.5">
              <span aria-hidden className="text-surface-300">
                →
              </span>
              <span
                className={clsx(
                  "inline-flex items-center gap-1 rounded-full px-2.5 py-1",
                  person ? "bg-primary-100 font-semibold text-primary-800" : "bg-surface-100 text-surface-700",
                )}
              >
                <P.icon size={11} /> {P.title}
                {b.nodes.length > 1 && <span className="text-surface-500">· {b.nodes.length}</span>}
              </span>
            </li>
          );
        })}
      </ol>
      <p className="text-xs text-surface-500">
        {f.nodes.length} steps in {parts.length} phases · people decide at the end
        {tollgates > 0 &&
          `, and approve the work ${tollgates === 1 ? "once" : `${tollgates} times`} on the way (a tollgate)`}
        .
      </p>

      <ol className="relative space-y-3 border-l-2 border-surface-200 pl-5">
        <li className="relative">
          <span className="absolute -left-[1.85rem] top-1 flex h-5 w-5 items-center justify-center rounded-full bg-surface-200 text-surface-700">
            <CalendarClock size={11} />
          </span>
          <p className="text-sm font-semibold text-surface-900">A case opens</p>
          <p className="text-xs text-surface-600">
            {opensText(f.opens)}
            {f.opens.events && f.opens.on !== "event" && "; other systems may also open one by event"}.
          </p>
        </li>
        {parts.map((b, i) => {
          const P = PHASES[b.phase];
          const person = b.phase === "people";
          return (
            <li key={i} className="relative">
              <span
                className={clsx(
                  "absolute -left-[1.85rem] top-3 flex h-5 w-5 items-center justify-center rounded-full text-[10px] font-bold",
                  person ? "bg-primary-600 text-white" : "bg-surface-700 text-white",
                )}
              >
                {i + 1}
              </span>
              <section
                className={clsx("rounded-xl border bg-card", person ? "border-primary-300" : "border-surface-200")}
              >
                <header className="flex flex-wrap items-baseline gap-x-2 gap-y-0.5 border-b border-surface-100 px-4 py-2.5">
                  <h3 className="text-sm font-semibold text-surface-900">{P.title}</h3>
                  <span
                    className={clsx(
                      "inline-flex items-center gap-1 text-xs",
                      person ? "font-medium text-primary-700" : "text-surface-500",
                    )}
                  >
                    <P.icon size={11} /> {P.who}
                  </span>
                  <p className="w-full text-xs text-surface-500">{P.says}</p>
                </header>
                <ul className="divide-y divide-surface-100">
                  {b.nodes.map((n) => {
                    const { name, kind, says } = nameOf(n);
                    const notes = n.notes.filter((t) => t !== TYPE[n.type ?? ""]?.label);
                    return (
                      <li key={n.id}>
                        {n.pause && n.id !== "review" && (
                          <p className="flex items-center gap-1.5 bg-primary-50 px-4 py-1.5 text-xs font-medium text-primary-800">
                            <Hand size={12} /> Tollgate: the run stops here until a person approves the work so far
                          </p>
                        )}
                        <div
                          className="grid gap-1 px-4 py-2 text-sm sm:grid-cols-[minmax(0,16rem)_1fr]"
                          data-testid={`flow-${n.id}`}
                        >
                          <div>
                            <span className="font-medium text-surface-900">{name}</span>
                            {n.gate && (
                              <span className="ml-1.5 inline-flex items-center gap-0.5 text-[10px] text-primary-700">
                                <ShieldCheck size={10} /> always on
                              </span>
                            )}
                            {kind && <span className="block text-[11px] text-surface-500">{kind}</span>}
                          </div>
                          <div className="min-w-0 text-xs text-surface-600">
                            {says && <p>{says}</p>}
                            {(n.tools.length > 0 || notes.length > 0 || n.people.length > 0) && (
                              <p className="mt-0.5 flex flex-wrap items-center gap-x-2 gap-y-0.5">
                                {n.tools.map((t) => (
                                  <span
                                    key={t}
                                    className="inline-flex items-center gap-1 font-mono text-[11px] text-surface-700"
                                  >
                                    <Wrench size={10} /> {t}
                                  </span>
                                ))}
                                {notes.map((t) => (
                                  <span key={t} className="text-surface-500">
                                    {t}
                                  </span>
                                ))}
                                {n.people.length > 0 && (
                                  <span className="inline-flex items-center gap-1 font-medium text-primary-700">
                                    <Users size={10} /> {n.people.join(", ")}
                                  </span>
                                )}
                              </p>
                            )}
                          </div>
                        </div>
                      </li>
                    );
                  })}
                </ul>
              </section>
            </li>
          );
        })}
      </ol>
      <p className="text-[11px] text-surface-500">
        Drawn from the configuration (version shown above). <Wrench size={10} className="inline" /> a system read
        through the gateway ·
        <ShieldCheck size={10} className="mx-0.5 inline" /> a gate no one can remove ·{" "}
        <Hand size={10} className="mx-0.5 inline" /> where the run waits for a person.
      </p>
    </div>
  );
}
