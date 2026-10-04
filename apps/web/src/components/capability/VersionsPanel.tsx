// Versions: who drafted and approved each, what changed between any two
// (the diff an approver reads), and export for promotion to another environment.

import { useState } from "react";
import { Download } from "lucide-react";

import { api } from "../../api/client";
import { useDiff, type CapabilityVersion } from "../../api/helix";
import StatusBadge from "../StatusBadge";
import { formatTime } from "../ui";

export default function VersionsPanel({ capabilityId, versions, group }: {
  capabilityId: string;
  versions: CapabilityVersion[];
  group?: string | null;
}) {
  const sorted = [...versions].sort((x, y) => x.version - y.version);
  const [a, setA] = useState<number | null>(sorted.length > 1 ? sorted[sorted.length - 2].version : null);
  const [b, setB] = useState<number | null>(sorted.length ? sorted[sorted.length - 1].version : null);
  const diff = useDiff(capabilityId, a, b, group);

  const exportVersion = async (v: number) => {
    const bundle = await api.get<unknown>(
      `/capabilities/${encodeURIComponent(capabilityId)}/versions/${v}/export${group ? `?group=${encodeURIComponent(group)}` : ""}`,
    );
    const url = URL.createObjectURL(new Blob([JSON.stringify(bundle, null, 2)], { type: "application/json" }));
    Object.assign(document.createElement("a"), { href: url, download: `${capabilityId}${group ? `-${group}` : ""}-v${v}.helix.json` }).click();
    setTimeout(() => URL.revokeObjectURL(url), 1000);
  };

  return (
    <div className="space-y-3">
      <ul className="divide-y divide-surface-100 text-sm">
        {sorted.slice().reverse().map((v) => (
          <li key={v.version} className="flex flex-wrap items-center gap-3 py-2">
            <span className="font-mono text-xs">v{v.version}</span>
            <StatusBadge status={v.status} />
            <span className="text-surface-600">{v.note || "—"}</span>
            <span className="ml-auto text-xs text-surface-500">
              drafted by {v.drafted_by} {formatTime(v.drafted_at)}
              {v.decided_by && <> · approved by {v.decided_by}</>}
            </span>
            <button onClick={() => void exportVersion(v.version)} title="Export for another environment"
              className="text-surface-400 hover:text-primary-700" aria-label={`Export v${v.version}`}>
              <Download size={14} />
            </button>
          </li>
        ))}
      </ul>
      {sorted.length > 1 && (
        <div>
          <div className="mb-2 flex items-center gap-2 text-xs text-surface-600">
            Compare
            <select aria-label="From version" value={a ?? ""} onChange={(e) => setA(Number(e.target.value))} className="rounded-md border border-surface-300 px-2 py-1">
              {sorted.map((v) => <option key={v.version} value={v.version}>v{v.version}</option>)}
            </select>
            with
            <select aria-label="To version" value={b ?? ""} onChange={(e) => setB(Number(e.target.value))} className="rounded-md border border-surface-300 px-2 py-1">
              {sorted.map((v) => <option key={v.version} value={v.version}>v{v.version}</option>)}
            </select>
            {diff.data && <span className="min-w-0 break-words text-surface-500 [overflow-wrap:anywhere]">changed: {diff.data.changed.join(", ") || "nothing"}</span>}
          </div>
          {diff.data && (
            <pre aria-label="Version diff" className="max-h-96 overflow-auto rounded-lg bg-code-bg p-3 font-mono text-[11px] leading-relaxed text-code-fg">
              {diff.data.diff.split("\n").map((line, i) => (
                <span key={i} className={line.startsWith("+") && !line.startsWith("+++") ? "text-green-300"
                  : line.startsWith("-") && !line.startsWith("---") ? "text-red-300" : undefined}>
                  {line}
                  {"\n"}
                </span>
              ))}
            </pre>
          )}
        </div>
      )}
    </div>
  );
}
