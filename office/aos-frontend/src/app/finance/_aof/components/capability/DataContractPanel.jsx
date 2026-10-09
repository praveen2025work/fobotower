// Generated from apps/web/src/components/capability/DataContractPanel.tsx by apps/web/office/convert.mjs. Office changes to this file are
// kept by aof_sync.py on the next update; see office/README.md.
// What the configuration needs: the data fields it reads (and what reads
// each), and the parameters still to confirm — derived from the configuration,
// so it is always the contract the next run will hold the data to.

import { useState } from "react";
import { Database } from "lucide-react";

import { useDataContract } from "../../api/aof";
import { Card, ErrorState, Loading } from "../ui";

export default function DataContractPanel({ capabilityId, teamGroup }) {
  const q = useDataContract(capabilityId, teamGroup);
  const [all, setAll] = useState(false);
  const d = q.data;
  const fromData = d?.data.filter((f) => !f.derived) ?? [];
  return (
    <Card
      title={
        <span className="flex items-center gap-2">
          <Database size={14} /> Data and parameters
        </span>
      }
    >
      {q.isLoading && <Loading what="the data contract" />}
      {q.error && <ErrorState error={q.error} />}
      {d && (
        <div className="space-y-4">
          <section aria-label="Parameters">
            <h3 className="mb-1 text-xs font-semibold uppercase tracking-wider text-surface-500">
              Parameters{" "}
              {d.to_confirm.length > 0 && (
                <span className="ml-1 rounded bg-orange-100 px-1.5 text-orange-800">
                  {d.to_confirm.length} to confirm
                </span>
              )}
            </h3>
            {d.parameters.length === 0 ? (
              <p className="text-xs text-surface-500">None.</p>
            ) : (
              <table className="w-full text-left text-xs">
                <tbody className="divide-y divide-surface-100">
                  {d.parameters.map((p) => (
                    <tr key={p.name}>
                      <td className="py-1 pr-2 font-medium text-surface-800">{p.name.replace(/_/g, " ")}</td>
                      <td className="py-1 pr-2">
                        {p.to_confirm ? (
                          <span className="rounded bg-orange-100 px-1.5 font-semibold text-orange-800">to confirm</span>
                        ) : (
                          <span className="tabular-nums">
                            {String(p.value)}
                            {p.unit ? ` ${p.unit}` : ""}
                          </span>
                        )}
                      </td>
                      <td className="py-1 text-surface-500">
                        {p.used_by.length ? p.used_by.join("; ") : "not used by any rule yet"}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            )}
          </section>
          <section aria-label="Data needed">
            <h3 className="mb-1 text-xs font-semibold uppercase tracking-wider text-surface-500">
              Data needed from {d.source}
              {d.enrich.length ? ` and ${d.enrich.join(", ")}` : ""} ({fromData.length} fields)
            </h3>
            <p className="mb-1 text-xs text-surface-500">
              A field missing at run time makes the check that reads it negative and the test “not run”. Nothing is
              assumed.
            </p>
            <table className="w-full text-left text-xs">
              <tbody className="divide-y divide-surface-100">
                {(all ? d.data : fromData.slice(0, 12)).map((f) => (
                  <tr key={f.field}>
                    <td className="py-1 pr-2 font-mono text-surface-800">{f.field}</td>
                    <td className="py-1 pr-2 text-surface-500">{f.from}</td>
                    <td className="py-1 text-surface-600">{f.used_by.join("; ")}</td>
                  </tr>
                ))}
              </tbody>
            </table>
            {(fromData.length > 12 || d.data.length > fromData.length) && (
              <button onClick={() => setAll(!all)} className="mt-1 text-xs text-primary-700 hover:underline">
                {all ? "Show fewer" : `Show all ${d.data.length}, with what Agent One Finance computes`}
              </button>
            )}
          </section>
        </div>
      )}
    </Card>
  );
}
