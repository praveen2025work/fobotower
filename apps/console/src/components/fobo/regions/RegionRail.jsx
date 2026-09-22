'use client';

import { useMemo, useState } from 'react';

import {
  ChevronDownIcon,
  ChevronRightIcon,
  ChevronsLeftIcon,
  ChevronsRightIcon,
  PinIcon,
} from '@/components/fobo/icons';

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

/**
 * The rail closes when a rec is selected, unless it is pinned. On a wide
 * screen the extra 260px matters more than the rail does once you have
 * chosen what to look at — but a controller comparing recs needs it to
 * stay, hence the pin.
 */
export default function RegionRail({
  regions,
  selectedRecId,
  onSelectRec,
  pinned,
  onTogglePin,
  collapsed,
  onToggleCollapse,
}) {
  const [query, setQuery] = useState('');
  const [closedRegions, setClosedRegions] = useState(() => new Set());

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

  if (collapsed) {
    return (
      <aside className="glass-card p-2 self-start flex flex-col items-center gap-2">
        <button
          type="button"
          onClick={onToggleCollapse}
          aria-label="Expand nav"
          title="Expand nav"
          className="rounded p-1"
          style={{ color: 'var(--text-secondary)' }}
        >
          <ChevronsRightIcon />
        </button>
        {regions.map(({ region }) => (
          <span
            key={region}
            title={region}
            className="flex items-center justify-center rounded-full text-[10px] font-bold"
            style={{ width: 24, height: 24, ...REGION_STYLE[region] }}
          >
            {region[0]}
          </span>
        ))}
      </aside>
    );
  }

  function toggleRegion(region) {
    setClosedRegions((prev) => {
      const next = new Set(prev);
      if (next.has(region)) next.delete(region);
      else next.add(region);
      return next;
    });
  }

  return (
    <aside className="glass-card p-3 flex flex-col gap-2 self-start">
      <div className="flex items-center gap-2">
        <h2
          className="text-xs font-bold tracking-wide"
          style={{
            color: 'var(--text-primary)',
            fontFamily: 'var(--font-manrope), sans-serif',
          }}
        >
          REGIONS &amp; RECS
        </h2>
        <div className="ml-auto flex items-center gap-1">
          <button
            type="button"
            onClick={onTogglePin}
            aria-label="Pin nav"
            aria-pressed={pinned}
            title={pinned ? 'Unpin nav' : 'Pin nav'}
            className="rounded p-1 flex items-center"
            style={{
              color: pinned ? 'var(--clr-blue)' : 'var(--text-muted)',
              background: pinned ? 'var(--bg-active)' : 'transparent',
            }}
          >
            <PinIcon filled={pinned} />
          </button>
          <button
            type="button"
            onClick={onToggleCollapse}
            aria-label="Collapse nav"
            title="Collapse nav"
            className="rounded p-1 flex items-center"
            style={{ color: 'var(--text-muted)' }}
          >
            <ChevronsLeftIcon />
          </button>
        </div>
      </div>

      <input
        type="search"
        value={query}
        placeholder="Search recs…"
        onChange={(e) => setQuery(e.target.value)}
        className="w-full rounded-lg px-3 py-1.5 text-sm outline-none"
        style={{
          background: 'var(--bg-muted)',
          border: '1px solid var(--border-subtle)',
          color: 'var(--text-primary)',
        }}
      />

      <p
        className="text-[11px] flex items-center gap-1"
        style={{ color: 'var(--text-muted)' }}
      >
        <PinIcon size={11} filled={pinned} />
        {pinned
          ? 'Pinned. Stays open on select.'
          : 'Closes on select. Pin to keep open.'}
      </p>

      {filtered.length === 0 && (
        <p className="text-xs" style={{ color: 'var(--text-muted)' }}>
          No recs match.
        </p>
      )}

      {filtered.map(({ region, recs }) => {
        const closed = closedRegions.has(region);
        const pending = recs.reduce((n, r) => n + (r.adj_pending ?? 0), 0);
        return (
          <div key={region} className="flex flex-col gap-1">
            <button
              type="button"
              onClick={() => toggleRegion(region)}
              aria-expanded={!closed}
              className="flex items-center gap-2 w-full text-left py-0.5"
            >
              <span
                className="flex items-center shrink-0"
                style={{ color: 'var(--text-muted)', width: 12 }}
              >
                {closed ? <ChevronRightIcon /> : <ChevronDownIcon />}
              </span>
              <span
                className="flex items-center justify-center rounded-full text-[10px] font-bold shrink-0"
                style={{ width: 20, height: 20, ...REGION_STYLE[region] }}
              >
                {region[0]}
              </span>
              <span
                className="text-xs font-semibold"
                style={{ color: 'var(--text-primary)' }}
              >
                {region}
              </span>
              <span className="ml-auto flex items-center gap-1">
                {pending > 0 && (
                  <span
                    className="pill"
                    aria-label={`${pending} adjustments pending in ${region}`}
                    style={{
                      background: 'var(--clr-purple-bg)',
                      color: 'var(--clr-purple)',
                    }}
                  >
                    {pending}
                  </span>
                )}
                <span
                  className="pill"
                  aria-label={`${recs.length} recs in ${region}`}
                  style={{
                    background: 'var(--bg-hover)',
                    color: 'var(--text-muted)',
                  }}
                >
                  {recs.length}
                </span>
              </span>
            </button>

            {!closed &&
              recs.map((rec) => (
                <RecRow
                  key={rec.rec_id}
                  rec={rec}
                  selected={rec.rec_id === selectedRecId}
                  onSelect={() => onSelectRec(rec.rec_id)}
                />
              ))}
          </div>
        );
      })}
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
          style={{ width: `${pct}%`, height: '100%', background: STATUS_BAR[rec.status] }}
        />
      </div>
    </button>
  );
}
