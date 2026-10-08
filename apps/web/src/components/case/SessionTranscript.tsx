// The skill session behind a case (the `agent` step), turn by turn: what the
// platform asked, what the model said, every tool it called and with what,
// what came back, and its final answer. Every tool call here is also an audit
// row under "Data used" — the conversation and the audit tell the same story.

import { useState } from "react";
import clsx from "clsx";
import { Bot, FileText, User, Wrench } from "lucide-react";

import type { SessionInfo, SessionTurn } from "../../api/aof";

function Args({ input }: { input?: Record<string, unknown> }) {
  if (!input) return null;
  return (
    <span className="text-surface-500">
      ({Object.entries(input).map(([k, v], i) => (
        <span key={k}>{i > 0 && ", "}{k}: <span className="text-surface-800">{String(v)}</span></span>
      ))})
    </span>
  );
}

function Prompt({ text }: { text?: string }) {
  const [open, setOpen] = useState(false);
  if (!text) return null;
  const long = text.length > 280;
  return (
    <div>
      <pre className="whitespace-pre-wrap break-words rounded border border-surface-200 bg-surface-50 p-2 font-mono text-[11px] text-surface-700">
        {open || !long ? text : `${text.slice(0, 280)}…`}
      </pre>
      {long && (
        <button onClick={() => setOpen(!open)} className="mt-1 text-[11px] text-primary-700 hover:underline">
          {open ? "show less" : "show all"}
        </button>
      )}
    </div>
  );
}

function Entry({ t }: { t: SessionTurn }) {
  const who = t.role === "user" ? "Agent One Finance" : t.role === "tool" ? "Tool" : "Model";
  const Icon = t.role === "user" ? User : t.role === "tool" ? Wrench : Bot;
  return (
    <li className="relative">
      <span className={clsx("absolute -left-[23px] top-0.5 rounded-full bg-card p-0.5",
        t.role === "model" ? "text-primary-600" : "text-surface-400")}>
        <Icon size={13} />
      </span>
      <div className="text-[11px] uppercase tracking-wide text-surface-500">
        {who}{t.turn > 0 && <span className="normal-case tracking-normal"> · turn {t.turn}</span>}
      </div>
      <div className="mt-0.5 text-sm text-surface-800">
        {t.kind === "prompt" && <Prompt text={t.text} />}
        {t.kind === "text" && <p className="whitespace-pre-wrap">{t.text}</p>}
        {t.kind === "tool_call" && (
          <p className="font-mono text-xs">
            calls <span className="font-semibold text-primary-700">{t.tool}</span> <Args input={t.input} />
          </p>
        )}
        {t.kind === "tool_result" && (
          <p className={clsx("text-xs", t.error ? "text-red-700" : "text-surface-600")}>
            {t.error ? `refused: ${t.text ?? ""}` : t.rows == null ? "answered" : `returned ${t.rows} row${t.rows === 1 ? "" : "s"}`}
            {t.tool && <span className="font-mono"> · {t.tool}</span>}
          </p>
        )}
        {t.kind === "answer" && (
          <p className="rounded border border-primary-200 bg-primary-50 px-2 py-1.5 text-sm text-primary-800">{t.text}</p>
        )}
      </div>
    </li>
  );
}

export default function SessionTranscript({ session }: { session: SessionInfo }) {
  const calls = session.transcript.filter((t) => t.kind === "tool_call").length;
  const facts: [string, string | number | undefined | null][] = [
    ["Model", session.model ? `${session.model} (${session.adapter})` : session.adapter],
    ["Session", session.session_id],
    ["Turns", session.turns],
    ["Tool calls", calls],
    ["Results", session.results],
    ["Cost", session.cost_usd != null ? `$${session.cost_usd.toFixed(4)}` : undefined],
  ];
  return (
    <div className="space-y-4">
      <div className="rounded-lg border border-surface-200 p-3">
        <p className="text-sm text-surface-700">
          One model session ran this case: the skill, the case key and only the tools below. Each tool call went
          through the gateway and is an audit row under <em>Data used</em>.
        </p>
        <dl className="mt-2 grid grid-cols-2 gap-x-4 gap-y-1 text-xs sm:grid-cols-3">
          {facts.filter(([, v]) => v !== undefined && v !== null && v !== "").map(([k, v]) => (
            <div key={k} className="flex justify-between gap-2"><dt className="text-surface-500">{k}</dt><dd className="font-medium text-surface-800">{v}</dd></div>
          ))}
        </dl>
        <div className="mt-2 flex flex-wrap items-center gap-1.5 text-[11px]">
          <FileText size={12} className="text-surface-500" />
          <span className="text-surface-600">Skill: {session.skill_file ?? "inline instructions"} · {session.skill_chars.toLocaleString()} characters</span>
          <span className="mx-1 text-surface-300">|</span>
          {session.tools.map((tool) => (
            <span key={tool} className="rounded bg-surface-100 px-1.5 py-0.5 font-mono text-surface-700">{tool}</span>
          ))}
        </div>
        {session.failure && <p className="mt-2 text-xs text-red-700">The session failed: {session.failure}</p>}
      </div>
      <ol className="relative space-y-3 border-l border-surface-200 pl-4" aria-label="Model session">
        {session.transcript.map((t, i) => <Entry key={i} t={t} />)}
      </ol>
    </div>
  );
}
