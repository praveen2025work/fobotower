'use client';

import { useMemo, useState } from 'react';

const REGION_STYLE = {
  APAC: { background: 'var(--apac-bg)', color: 'var(--apac-text)' },
  EMEA: { background: 'var(--emea-bg)', color: 'var(--emea-text)' },
  AMER: { background: 'var(--amer-bg)', color: 'var(--amer-text)' },
};

const STATUS_BAR = {
  cleared: 'var(--bar-cleared)',
  awaiting: 'var(--bar-awaiting)',
  blocked: 'var(--bar-blocked)',
  in_progress: 'var(--bar-analysing)',
  scheduled: 'var(--bar-notopen)',
};

export default function RegionRail({ regions, selectedRecId, onSelectRec }) {
  const [query, setQuery] = useState('');

  const filtered = useMemo(() => {
    const needle = query.trim().toLowerCase();
    if (!needle) return regions;
    return regions
      .map((r) => ({
        ...r,
        recs: r.recs.filter((rec) => rec.name.toLowerCase().includes(needle)),
      }))
      .filter((r) => r.recs.length > 0);
  }, [regions, query]);

  return (
    <aside className="glass-card p-3 flex flex-col gap-3 self-start">
      <h2
        className="text-xs font-bold tracking-wide"
        style={{ color: 'var(--text-primary)', fontFamily: 'Manrope, sans-serif' }}
      >
        REGIONS &amp; RECS
      </h2>

      <input
        type="search"
        value={query}
        placeholder="Search recs..."
        onChange={(e) => setQuery(e.target.value)}
        className="w-full rounded-lg px-3 py-1.5 text-sm outline-none"
        style={{
          background: 'var(--bg-muted)',
          border: '1px solid var(--border-subtle)',
          color: 'var(--text-primary)',
        }}
      />

      {filtered.length === 0 && (
        <p className="text-xs" style={{ color: 'var(--text-muted)' }}>
          No recs match.
        </p>
      )}

      {filtered.map(({ region, recs }) => (
        <div key={region} className="flex flex-col gap-1">
          <span
            className="pill font-semibold self-start"
            style={REGION_STYLE[region]}
          >
            {region}
          </span>
          {recs.map((rec) => (
            <RecRow
              key={rec.rec_id}
              rec={rec}
              selected={rec.rec_id === selectedRecId}
              onSelect={() => onSelectRec(rec.rec_id)}
            />
          ))}
        </div>
      ))}
    </aside>
  );
}

function RecRow({ rec, selected, onSelect }) {
  const pct =
    rec.books_total === 0
      ? 0
      : Math.round((rec.books_open / rec.books_total) * 100);

  return (
    <button
      type="button"
      onClick={onSelect}
      aria-pressed={selected}
      className="w-full text-left rounded-lg px-2 py-1.5 transition"
      style={{
        background: selected ? 'var(--bg-active)' : 'transparent',
        border: `1px solid ${selected ? 'var(--clr-blue)' : 'transparent'}`,
      }}
    >
      <div className="flex items-center justify-between gap-2">
        <span className="text-sm truncate" style={{ color: 'var(--text-primary)' }}>
          {rec.name}
        </span>
        {rec.adj_pending > 0 && (
          <span
            className="pill shrink-0"
            aria-label={`${rec.adj_pending} adjustments pending`}
            style={{
              background: 'var(--clr-purple-bg)',
              color: 'var(--clr-purple)',
            }}
          >
            {rec.adj_pending}
          </span>
        )}
      </div>
      <div className="text-xs mt-0.5" style={{ color: 'var(--text-muted)' }}>
        {rec.scheduled} IST · {rec.books_open}/{rec.books_total} open
      </div>
      <div
        className="mt-1 h-1 rounded-full overflow-hidden"
        style={{ background: 'var(--bar-notopen)' }}
      >
        <div
          style={{
            width: `${pct}%`,
            height: '100%',
            background: STATUS_BAR[rec.status],
          }}
        />
      </div>
    </button>
  );
}
