'use client';

import { useEffect } from 'react';

import { useFoboAnalyticsStore } from '@/store/foboAnalyticsStore';

const STATUS_COLOR = {
  cleared: 'var(--bar-cleared)',
  awaiting: 'var(--bar-awaiting)',
  blocked: 'var(--bar-blocked)',
  in_progress: 'var(--bar-analysing)',
  scheduled: 'var(--bar-notopen)',
};

const STATUS_ORDER = ['cleared', 'awaiting', 'in_progress', 'blocked', 'scheduled'];

/**
 * Every tile shows its own basis. A headline number with no stated
 * derivation is a number nobody can check, and these are exactly the
 * figures someone will quote in a steering meeting.
 */
function Tile({ label, value, suffix, basis }) {
  return (
    <div className="glass-card p-3 flex flex-col gap-0.5">
      <div
        className="text-[11px] font-bold tracking-wide"
        style={{ color: 'var(--text-muted)' }}
      >
        {label}
      </div>
      <div
        className="text-2xl font-bold"
        style={{
          color: value === null ? 'var(--text-muted)' : 'var(--text-primary)',
          fontFamily: 'var(--font-manrope), sans-serif',
        }}
      >
        {value === null ? '—' : value}
        {value !== null && suffix ? (
          <span className="text-base font-semibold"> {suffix}</span>
        ) : null}
      </div>
      <div className="text-[11px]" style={{ color: 'var(--text-muted)' }}>
        {basis}
      </div>
    </div>
  );
}

function StackedBars({ rows }) {
  const statuses = STATUS_ORDER.filter((s) => rows.some((r) => r[s]));
  const max = Math.max(
    1,
    ...rows.map((r) => statuses.reduce((n, s) => n + (r[s] ?? 0), 0)),
  );
  return (
    <section className="glass-card p-3 flex flex-col gap-2">
      <h3 className="text-xs font-bold" style={{ color: 'var(--text-primary)' }}>
        Recs by region &amp; status
      </h3>
      {rows.map((r) => {
        const total = statuses.reduce((n, s) => n + (r[s] ?? 0), 0);
        return (
          <div key={r.region} className="flex items-center gap-2">
            <span
              className="text-xs w-12 shrink-0"
              style={{ color: 'var(--text-muted)' }}
            >
              {r.region}
            </span>
            <div
              className="flex h-4 rounded overflow-hidden flex-1"
              style={{ background: 'var(--bg-muted)' }}
            >
              {statuses.map((s) =>
                r[s] ? (
                  <div
                    key={s}
                    title={`${s}: ${r[s]}`}
                    style={{
                      width: `${(r[s] / max) * 100}%`,
                      background: STATUS_COLOR[s],
                    }}
                  />
                ) : null,
              )}
            </div>
            <span
              className="text-xs w-6 text-right shrink-0"
              style={{ color: 'var(--text-muted)' }}
            >
              {total}
            </span>
          </div>
        );
      })}
      <ul className="flex flex-wrap gap-3 text-[11px] mt-1">
        {statuses.map((s) => (
          <li key={s} className="flex items-center gap-1">
            <span
              aria-hidden="true"
              style={{
                width: 7,
                height: 7,
                borderRadius: '50%',
                background: STATUS_COLOR[s],
              }}
            />
            <span style={{ color: 'var(--text-muted)' }}>
              {s.replace('_', ' ')}
            </span>
          </li>
        ))}
      </ul>
    </section>
  );
}

function AutoManualSplit({ rows }) {
  const total = rows.reduce((n, r) => n + r.value, 0) || 1;
  const colors = { Auto: 'var(--bar-auto)', Manual: 'var(--clr-grey)' };
  return (
    <section className="glass-card p-3 flex flex-col gap-2">
      <h3 className="text-xs font-bold" style={{ color: 'var(--text-primary)' }}>
        Adjustments — auto vs manual
      </h3>
      <div
        className="flex h-4 rounded overflow-hidden"
        style={{ background: 'var(--bg-muted)' }}
      >
        {rows.map((r) =>
          r.value ? (
            <div
              key={r.name}
              title={`${r.name}: ${r.value}`}
              style={{
                width: `${(r.value / total) * 100}%`,
                background: colors[r.name],
              }}
            />
          ) : null,
        )}
      </div>
      <ul className="flex gap-4 text-xs">
        {rows.map((r) => (
          <li key={r.name} className="flex items-center gap-1.5">
            <span
              aria-hidden="true"
              style={{
                width: 7,
                height: 7,
                borderRadius: '50%',
                background: colors[r.name],
              }}
            />
            <strong style={{ color: 'var(--text-primary)' }}>{r.value}</strong>
            <span style={{ color: 'var(--text-muted)' }}>
              {r.name} ({Math.round((r.value / total) * 100)}%)
            </span>
          </li>
        ))}
      </ul>
    </section>
  );
}

function GroundingByRun({ rows }) {
  return (
    <section className="glass-card p-3 flex flex-col gap-2">
      <h3 className="text-xs font-bold" style={{ color: 'var(--text-primary)' }}>
        Grounding pass rate by run
      </h3>
      <div className="flex items-end gap-3 h-24">
        {rows.map((r) => (
          <div key={r.window} className="flex-1 flex flex-col items-center gap-1">
            <div
              className="w-full rounded-t"
              style={{
                height: `${r.pass_rate ?? 0}%`,
                background: 'var(--clr-blue)',
                minHeight: 2,
              }}
              title={`${r.window}: ${r.pass_rate ?? '—'}%`}
            />
            <span className="text-[10px]" style={{ color: 'var(--text-muted)' }}>
              {r.window}
            </span>
          </div>
        ))}
      </div>
    </section>
  );
}

export default function AnalyticsTab() {
  const { data, loading, error, load } = useFoboAnalyticsStore();

  useEffect(() => {
    load();
  }, [load]);

  if (error) {
    return (
      <p className="p-4 text-sm" style={{ color: 'var(--clr-red)' }}>
        {error}
      </p>
    );
  }
  if (loading || !data) {
    return (
      <p className="p-4 text-sm" style={{ color: 'var(--text-muted)' }}>
        Loading analytics…
      </p>
    );
  }

  const saved = data.decisions_saved;

  return (
    <div className="flex flex-col gap-3">
      <div
        className="grid gap-3"
        style={{ gridTemplateColumns: 'repeat(auto-fit, minmax(180px, 1fr))' }}
      >
        <Tile
          label="GROUNDING PASS RATE"
          value={data.grounding_pass_rate.value}
          suffix="%"
          basis={data.grounding_pass_rate.basis}
        />
        <Tile
          label="DRAFT ACCEPTANCE"
          value={data.draft_acceptance.value}
          suffix="%"
          basis={data.draft_acceptance.basis}
        />
        <Tile
          label="DECISIONS SAVED"
          value={`${saved.from}→${saved.to}`}
          basis={saved.basis}
        />
        <Tile
          label="AVG. DRAFT → SIGN-OFF"
          value={data.median_signoff_minutes.value}
          suffix="min"
          basis={data.median_signoff_minutes.basis}
        />
        <Tile
          label="EST. HOURS SAVED"
          value={data.hours_saved.value}
          suffix="hrs"
          basis={data.hours_saved.basis}
        />
      </div>

      <div
        className="grid gap-3 items-start"
        style={{ gridTemplateColumns: 'repeat(auto-fit, minmax(280px, 1fr))' }}
      >
        <StackedBars rows={data.recs_by_region} />
        <GroundingByRun rows={data.grounding_by_run} />
        <AutoManualSplit rows={data.auto_vs_manual} />
      </div>

      <section className="glass-card p-3">
        <h3
          className="text-xs font-bold mb-1"
          style={{ color: 'var(--text-primary)' }}
        >
          Why these numbers matter
        </h3>
        <ul
          className="text-xs leading-relaxed flex flex-col gap-1"
          style={{ color: 'var(--text-secondary)' }}
        >
          <li>
            <strong>Grounding pass rate</strong> measures retrieval, not model
            confidence. A figure that could not be traced to source data is
            flagged rather than quietly rendered.
          </li>
          <li>
            <strong>Decisions saved</strong> is the efficiency claim: breaks
            that would each have needed a decision, against the patterns they
            collapsed into.
          </li>
          <li>
            <strong>Est. hours saved</strong> rests on an assumption — the
            minutes a manual decision would have taken — which is stated on
            the tile rather than hidden inside it.
          </li>
        </ul>
      </section>
    </div>
  );
}
