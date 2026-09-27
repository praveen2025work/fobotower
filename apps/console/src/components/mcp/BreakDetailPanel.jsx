import { ShieldAlert } from 'lucide-react';
import { breakDetail } from '../lib/breakDetail';
import { mono } from '../lib/format';
import { Callout, KvCards, VerifyList } from './Blocks';

export function BreakDetailPanel({ adj: adj2, rec }) {
  const d = breakDetail(adj2, rec);
  return (
    <div
      className="border-t px-3 py-3"
      style={{
        backgroundColor: 'var(--bg-muted)',
        borderColor: 'var(--border-subtle)',
      }}
    >
      <div className="flex items-center gap-2 flex-wrap mb-2.5">
        <span
          className="pill"
          style={{
            background: 'var(--clr-amber-bg)',
            color: 'var(--clr-amber)',
            fontSize: 10,
          }}
        >
          {d.type}
        </span>
        <span
          className="text-[10px]"
          style={{
            color: 'var(--text-muted)',
            ...mono,
          }}
        >
          {d.ref}
        </span>
        <span
          className="ml-auto text-[12px] font-bold tabular-nums"
          style={{
            color: 'var(--text-primary)',
            ...mono,
          }}
        >
          {d.delta}
        </span>
      </div>
      <p
        className="text-[12px] leading-relaxed mb-2.5"
        style={{
          color: 'var(--text-secondary)',
        }}
      >
        {d.cause}
      </p>
      <KvCards items={[d.cats, d.motif, d.gap]} />
      {d.fix ? (
        <Callout tone="ok" title="Proposed fix" text={d.fix} />
      ) : (
        <Callout
          tone="risk"
          text="No posting proposed. Manual investigation needed before any adjustment is made."
        />
      )}
      <VerifyList items={d.verify} />
      {!d.grounded && (
        <div
          className="flex items-center gap-1.5 mt-2 text-[11px]"
          style={{
            color: 'var(--clr-red)',
          }}
        >
          <ShieldAlert size={12} />
          One figure in the drafted adjustment could not be traced back to these
          values. Verify manually.
        </div>
      )}
    </div>
  );
}
