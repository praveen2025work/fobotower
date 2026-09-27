import { useState } from 'react';
import { Terminal } from 'lucide-react';
import { mono, sessionIdOf } from '../lib/format';
import { DataTable } from '../mcp/DataTable';
import { Drawer } from '../ui/Drawer';

export function McpInspector({ rec, calls, focusId, onClose }) {
  const [sel, setSel] = useState(focusId || (calls[0] && calls[0].id));
  const [q, setQ] = useState('');
  const call = calls.find((c) => c.id === sel) || calls[0];
  const rows = call
    ? call.rows.filter(
        (r) =>
          !q ||
          Object.values(r).some((v) =>
            String(v).toLowerCase().includes(q.toLowerCase()),
          ),
      )
    : [];
  const toCsv = () => {
    const head = call.columns.map((c) => c.label).join(',');
    const body = call.rows
      .map((r) =>
        call.columns
          .map((c) => {
            var _a;
            return `"${String((_a = r[c.key]) != null ? _a : '').replace(/"/g, '""')}"`;
          })
          .join(','),
      )
      .join('\n');
    navigator.clipboard &&
      navigator.clipboard.writeText(`${head}
${body}`);
  };
  return (
    <Drawer
      title="MCP inspector"
      subtitle={`${sessionIdOf(rec)} · ${calls.length} calls`}
      width={820}
      onClose={onClose}
    >
      {!calls.length ? (
        <div
          className="py-10 text-center text-[12px]"
          style={{
            color: 'var(--text-muted)',
          }}
        >
          No MCP calls in this session yet.
        </div>
      ) : (
        <div className="flex gap-4 min-h-0 flex-col md:flex-row">
          <div className="md:w-[250px] shrink-0 hx-space-y-1">
            {calls.map((c, i) => (
              <button
                key={c.id}
                onClick={() => setSel(c.id)}
                className="w-full text-left rounded-lg px-2.5 py-2 min-w-0"
                style={
                  c.id === call.id
                    ? {
                        background: 'var(--bg-active)',
                        border: '1px solid var(--border)',
                      }
                    : {
                        border: '1px solid transparent',
                      }
                }
              >
                <div
                  className="text-[11px] font-semibold truncate"
                  style={{
                    ...mono,
                    color: 'var(--text-primary)',
                  }}
                >
                  {i + 1}
                  {'. '}
                  {c.server}.{c.tool}
                </div>
                <div
                  className="text-[10.5px] truncate"
                  style={{
                    color:
                      c.status === 'running'
                        ? 'var(--text-muted)'
                        : 'var(--clr-green)',
                  }}
                >
                  {c.summary}
                </div>
              </button>
            ))}
          </div>
          <div className="flex-1 min-w-0 hx-space-y-3">
            <div className="flex items-center gap-2 flex-wrap">
              <Terminal
                size={13}
                style={{
                  color: 'var(--barcl-eagle)',
                }}
              />
              <span
                className="text-[13px] font-bold"
                style={{
                  ...mono,
                  color: 'var(--text-primary)',
                }}
              >
                {call.server}.{call.tool}
              </span>
              {call.ms && (
                <span
                  className="pill"
                  style={{
                    background: 'var(--bg-muted)',
                    color: 'var(--text-muted)',
                  }}
                >
                  {call.ms}
                  {' ms'}
                </span>
              )}
              <span
                className="pill"
                style={{
                  background: 'var(--clr-green-bg)',
                  color: 'var(--clr-green)',
                }}
              >
                {call.rows.length}
                {' rows'}
              </span>
            </div>
            <div>
              <div
                className="text-[10.5px] font-semibold mb-1"
                style={{
                  color: 'var(--text-muted)',
                }}
              >
                Request
              </div>
              <pre
                className="text-[11px] rounded-lg px-3 py-2 overflow-x-auto"
                style={{
                  ...mono,
                  background: 'var(--bg-muted)',
                  color: 'var(--text-secondary)',
                  margin: 0,
                }}
              >
                {JSON.stringify(call.args, null, 2)}
              </pre>
            </div>
            <div>
              <div className="flex items-center gap-2 mb-1.5">
                <div
                  className="text-[10.5px] font-semibold"
                  style={{
                    color: 'var(--text-muted)',
                  }}
                >
                  Response data
                </div>
                <input
                  value={q}
                  onChange={(e) => setQ(e.target.value)}
                  placeholder="Filter rows"
                  className="ml-auto text-[11px] px-2 py-1 focus:outline-none w-40"
                  style={{
                    borderRadius: 'var(--radius-sm)',
                    border: '1px solid var(--border)',
                    background: 'var(--bg-muted)',
                    color: 'var(--text-primary)',
                  }}
                />
                <button
                  onClick={toCsv}
                  className="pill"
                  style={{
                    background: 'var(--bg-muted)',
                    color: 'var(--text-secondary)',
                    border: '1px solid var(--border)',
                  }}
                >
                  Copy CSV
                </button>
              </div>
              <DataTable columns={call.columns} rows={rows} />
            </div>
          </div>
        </div>
      )}
    </Drawer>
  );
}
