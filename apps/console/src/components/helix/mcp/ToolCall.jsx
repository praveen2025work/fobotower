import { useState } from 'react';
import { ChevronDown, ChevronRight, Terminal } from 'lucide-react';
import { TableIcon } from '../ui/icons';
import { mono } from '../lib/format';
import { DataTable } from './DataTable';

export function ToolCall({ call, onInspect, defaultOpen = false }) {
  const [open, setOpen] = useState(defaultOpen);
  const running = call.status === 'running';
  return (
    <div
      className="rounded-lg overflow-hidden"
      style={{
        border: '1px solid var(--border)',
        background: 'var(--bg-card-solid)',
      }}
    >
      <button
        onClick={() => !running && setOpen((o) => !o)}
        className="w-full flex items-center gap-2 px-2.5 py-1.5 text-left min-w-0"
        aria-expanded={open}
        disabled={running}
      >
        <Terminal
          size={11}
          className="shrink-0"
          style={{
            color: 'var(--barcl-eagle)',
          }}
        />
        <span
          className="text-[11px] font-semibold truncate"
          style={{
            ...mono,
            color: 'var(--text-primary)',
          }}
        >
          {call.server}.{call.tool}
        </span>
        <span
          className="text-[10.5px] truncate flex-1 min-w-0"
          style={{
            color: running ? 'var(--text-muted)' : 'var(--clr-green)',
          }}
        >
          {call.summary}
        </span>
        {call.ms && (
          <span
            className="text-[10px] tabular-nums shrink-0"
            style={{
              color: 'var(--text-muted)',
            }}
          >
            {call.ms}
            {' ms'}
          </span>
        )}
        {!running &&
          (open ? (
            <ChevronDown
              size={11}
              className="shrink-0"
              style={{
                color: 'var(--text-muted)',
              }}
            />
          ) : (
            <ChevronRight
              size={11}
              className="shrink-0"
              style={{
                color: 'var(--text-muted)',
              }}
            />
          ))}
      </button>
      {open && (
        <div className="px-2.5 pb-2.5 hx-space-y-2">
          <pre
            className="text-[10.5px] rounded-md px-2 py-1.5 overflow-x-auto"
            style={{
              ...mono,
              background: 'var(--bg-muted)',
              color: 'var(--text-secondary)',
              margin: 0,
            }}
          >
            {JSON.stringify(call.args, null, 1).replace(/\n\s*/g, ' ')}
          </pre>
          <DataTable columns={call.columns} rows={call.rows} max={6} />
          {onInspect && (
            <button
              onClick={() => onInspect(call.id)}
              className="flex items-center gap-1 text-[10.5px] hover:opacity-70"
              style={{
                color: 'var(--barcl-eagle)',
              }}
            >
              <TableIcon size={11} />
              Open in MCP inspector
            </button>
          )}
        </div>
      )}
    </div>
  );
}

export function CallList({ calls, onInspect, title }) {
  const [open, setOpen] = useState(false);
  if (!calls || !calls.length) return null;
  return (
    <div
      className="mt-2.5 pt-2"
      style={{
        borderTop: '1px solid var(--border-subtle)',
      }}
    >
      <button
        onClick={() => setOpen((o) => !o)}
        className="flex items-center gap-1.5 text-[10.5px] hover:opacity-70"
        style={{
          color: 'var(--text-muted)',
        }}
        aria-expanded={open}
      >
        <Terminal size={11} />
        <span>
          {title || 'MCP calls'}
          {' ('}
          {calls.length})
        </span>
        {open ? <ChevronDown size={11} /> : <ChevronRight size={11} />}
      </button>
      {open && (
        <div className="mt-2 hx-space-y-1.5">
          {calls.map((c) => (
            <ToolCall key={c.id} call={c} onInspect={onInspect} />
          ))}
        </div>
      )}
    </div>
  );
}
