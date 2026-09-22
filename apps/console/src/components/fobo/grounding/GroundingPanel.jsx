'use client';

import { useState } from 'react';

/**
 * "Grounding — MCP calls (5)".
 *
 * The workflow records one call per retrieval, which for a 14-break
 * population is dozens of rows. A controller wants to know which systems
 * were asked and what came back, so calls are folded by tool and their row
 * counts summed. A failed call is never folded away — it is listed on its
 * own, because a source failure is the one thing here that changes a
 * decision.
 */
function fold(calls) {
  const failures = calls.filter((c) => c.error);
  const ok = calls.filter((c) => !c.error);

  const byTool = new Map();
  for (const c of ok) {
    const prev = byTool.get(c.tool);
    if (prev) {
      prev.rows += c.row_count ?? 0;
      prev.count += 1;
    } else {
      byTool.set(c.tool, {
        tool: c.tool,
        application: c.application,
        params: c.params,
        rows: c.row_count ?? 0,
        count: 1,
        error: null,
      });
    }
  }
  return [...byTool.values(), ...failures.map((c) => ({
    tool: c.tool,
    application: c.application,
    params: c.params,
    rows: null,
    count: 1,
    error: c.error,
  }))];
}

function paramText(params) {
  return Object.entries(params ?? {})
    .map(([k, v]) => `${k}=${v}`)
    .join(', ');
}

export default function GroundingPanel({ calls }) {
  const [open, setOpen] = useState(false);
  const folded = fold(calls ?? []);
  if (folded.length === 0) return null;

  return (
    <section>
      <button
        type="button"
        onClick={() => setOpen((v) => !v)}
        aria-expanded={open}
        className="flex items-center gap-2 text-xs font-semibold"
        style={{ color: 'var(--text-secondary)' }}
      >
        <span aria-hidden="true">{open ? '▾' : '▸'}</span>
        Grounding — MCP calls ({folded.length})
      </button>

      {open && (
        <ul className="mt-2 flex flex-col gap-1.5">
          {folded.map((c) => (
            <li
              key={c.tool}
              className="rounded-lg px-3 py-2 text-xs"
              style={{
                background: 'var(--bg-muted)',
                border: '1px solid var(--border-subtle)',
              }}
            >
              <div
                style={{
                  fontFamily: 'var(--font-mono), monospace',
                  color: 'var(--text-primary)',
                }}
              >
                {c.tool}({paramText(c.params)})
              </div>
              <div className="mt-0.5 flex items-center gap-1.5">
                <span aria-hidden="true" style={{ color: 'var(--text-muted)' }}>
                  →
                </span>
                {c.error ? (
                  <span style={{ color: 'var(--clr-red)' }}>
                    unavailable — {c.error}
                  </span>
                ) : (
                  <span style={{ color: 'var(--text-secondary)' }}>
                    {c.rows} rows
                    {c.count > 1 ? ` across ${c.count} calls` : ''}
                  </span>
                )}
              </div>
            </li>
          ))}
        </ul>
      )}
    </section>
  );
}
