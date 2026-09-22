'use client';

import StatChipRow from './StatChipRow';

const REGION_STYLE = {
  APAC: { background: 'var(--apac-bg)', color: 'var(--apac-text)' },
  EMEA: { background: 'var(--emea-bg)', color: 'var(--emea-text)' },
  AMER: { background: 'var(--amer-bg)', color: 'var(--amer-text)' },
};

const STATUS_DOT = {
  cleared: 'var(--bar-cleared)',
  awaiting: 'var(--bar-awaiting)',
  blocked: 'var(--bar-blocked)',
  in_progress: 'var(--bar-analysing)',
  scheduled: 'var(--bar-notopen)',
};

/** "CATS vs MOTIF — Rates" reads as "Rates" in the timeline: the column
 *  is narrow and the rec family is already implied by the region row. */
function shortName(name) {
  return name.split('—').pop().trim();
}

export default function RunScheduleCard({
  stats,
  regions,
  runWindows,
  selectedRecId,
  onSelectRec,
}) {
  // One column for the region pill, then an equal column per run window.
  const columns = `56px repeat(${runWindows.length}, minmax(0, 1fr))`;

  return (
    <section className="glass-card px-4 py-3">
      <div className="flex flex-wrap items-baseline gap-x-3 gap-y-1">
        <h2
          className="text-xs font-bold tracking-wide shrink-0"
          style={{
            color: 'var(--text-primary)',
            fontFamily: 'var(--font-manrope), sans-serif',
          }}
        >
          RUN SCHEDULE — TODAY
        </h2>
        <span
          className="text-xs shrink-0"
          style={{ color: 'var(--text-muted)' }}
        >
          now {stats.now} {stats.timezone} · next {stats.next_run}
        </span>
        <div className="ml-auto">
          <StatChipRow stats={stats} />
        </div>
      </div>

      <div className="mt-3 grid gap-y-1.5" style={{ gridTemplateColumns: columns }}>
        <div />
        {runWindows.map((window, i) => (
          <div
            key={window}
            className="text-xs pb-1 pl-2"
            style={{
              color: 'var(--text-muted)',
              borderLeft: i === 0 ? 'none' : '1px solid var(--border-subtle)',
            }}
          >
            {window}
          </div>
        ))}

        {regions.map(({ region, recs }) => (
          <RegionRow
            key={region}
            region={region}
            recs={recs}
            runWindows={runWindows}
            selectedRecId={selectedRecId}
            onSelectRec={onSelectRec}
          />
        ))}
      </div>
    </section>
  );
}

function RegionRow({ region, recs, runWindows, selectedRecId, onSelectRec }) {
  return (
    <>
      <div className="pr-2 flex items-center">
        <span
          className="pill w-full text-center font-semibold"
          style={REGION_STYLE[region]}
        >
          {region}
        </span>
      </div>
      {runWindows.map((window, i) => (
        <div
          key={window}
          className="flex flex-wrap gap-1 py-0.5 pl-2"
          style={{
            borderLeft: i === 0 ? 'none' : '1px solid var(--border-subtle)',
          }}
        >
          {recs
            .filter((rec) => rec.scheduled === window)
            .map((rec) => (
              <RecChip
                key={rec.rec_id}
                rec={rec}
                selected={rec.rec_id === selectedRecId}
                onSelect={() => onSelectRec(rec.rec_id)}
              />
            ))}
        </div>
      ))}
    </>
  );
}

function RecChip({ rec, selected, onSelect }) {
  return (
    <button
      type="button"
      onClick={onSelect}
      aria-pressed={selected}
      title={`${rec.name} — ${rec.books_open}/${rec.books_total} open`}
      className="pill flex items-center gap-1.5 transition"
      style={{
        background: selected ? 'var(--bg-active)' : 'var(--bg-card-solid)',
        border: `1px solid ${selected ? 'var(--clr-amber)' : 'var(--border-subtle)'}`,
        color: 'var(--text-secondary)',
        boxShadow: selected ? '0 0 0 2px var(--clr-amber-bg)' : 'none',
      }}
    >
      <span
        aria-hidden="true"
        className="shrink-0"
        style={{
          width: 6,
          height: 6,
          borderRadius: '50%',
          background: STATUS_DOT[rec.status],
        }}
      />
      <span className="truncate">{shortName(rec.name)}</span>
      <span className="shrink-0" style={{ color: 'var(--text-muted)' }}>
        {rec.books_open}/{rec.books_total}
      </span>
    </button>
  );
}
