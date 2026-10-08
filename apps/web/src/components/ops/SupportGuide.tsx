// What platform support sees where case data would be: why it is empty, and
// what they can do instead. Support holds no data scope, so cases, reviews and
// their audit stay with the business teams.

import { Link } from "react-router-dom";
import { Activity, Plug, Power, ScrollText, ShieldCheck } from "lucide-react";

const DO = [
  { icon: Activity, text: "Check platform health, cost and errors", where: "Operations: the health strip", to: "/operations" },
  { icon: Plug, text: "See every connector and whether it answers", where: "Connectors", to: "/connectors" },
  { icon: Power, text: "Switch a capability or connector off during an incident", where: "Operations: Off switches", to: "/operations" },
  { icon: ScrollText, text: "Follow model behaviour (prompts, timings, tokens)", where: "Phoenix, by case id", to: null },
] as const;

/** A guided empty state for platform support. */
export default function SupportGuide({ what, className = "" }: { what: string; className?: string }) {
  return (
    <section aria-label="Platform support" className={`rounded-xl border border-surface-200 bg-card p-5 ${className}`}>
      <h2 className="flex items-center gap-2 text-sm font-semibold text-surface-900">
        <ShieldCheck size={16} className="text-primary-600" /> You are signed in as platform support
      </h2>
      <p className="mt-1 text-sm text-surface-600">
        {what} belong to the business teams, so they are not shown to you. Nothing is missing or broken.
      </p>
      <p className="mt-4 text-xs font-semibold uppercase tracking-wide text-surface-500">What you can do here</p>
      <ul className="mt-2 grid gap-2 sm:grid-cols-2">
        {DO.map(({ icon: Icon, text, where, to }) => (
          <li key={text} className="flex items-start gap-2.5 rounded-lg border border-surface-100 p-3 text-sm">
            <Icon size={15} className="mt-0.5 shrink-0 text-primary-600" />
            <span>
              <span className="text-surface-800">{text}</span>
              <span className="block text-xs text-surface-500">
                {to ? <Link to={to} className="text-primary-700 hover:underline">{where}</Link> : where}
              </span>
            </span>
          </li>
        ))}
      </ul>
    </section>
  );
}
