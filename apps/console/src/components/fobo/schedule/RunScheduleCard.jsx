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

const LANE_LABEL_WIDTH = 56;

/** "CATS vs MOTIF — Rates" reads as "Rates" in a lane: the rec family is
 *  already implied by the region it sits in. */
function shortName(name) {
  return name.split('—').pop().trim();
}

function toMinutes(hhmm) {
  const [h, m] = hhmm.split(':').map(Number);
  return h * 60 + m;
}

/**
 * Where a time sits along the lane, as a percentage.
 *
 * The lane spans the first run window to the last, with a margin at the end
 * so a chip scheduled in the final window still has room to render rather
 * than starting at the right edge.
 */
function positionFor(hhmm, windows) {
  if (windows.length < 2) return 0;
  const start = toMinutes(windows[0]);
  const end = toMinutes(windows[windows.length - 1]);
  const span = end - start || 1;
  const ratio = (toMinutes(hhmm) - start) / span;
  return Math.max(0, Math.min(1, ratio)) * 82;
}

export default function RunScheduleCard({
  stats,
  regions,
  runWindows,
  selectedRecId,
  onSelectRec,
}) {
  const nowPercent =
    stats.now && runWindows.length > 1 ? positionFor(stats.now, runWindows) : null;

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
        <span className="text-xs shrink-0" style={{ color: 'var(--text-muted)' }}>
          now {stats.now} {stats.timezone} · next {stats.next_run}
        </span>
        <div className="ml-auto">
          <StatChipRow stats={stats} />
        </div>
      </div>

      <div className="mt-3">
        {/* Time axis */}
        <div
          className="relative h-4"
          style={{ marginLeft: LANE_LABEL_WIDTH }}
        >
          {runWindows.map((window) => (
            <span
              key={window}
              className="absolute text-xs"
              style={{
                left: `${positionFor(window, runWindows)}%`,
                color: 'var(--text-muted)',
              }}
            >
              {window}
            </span>
          ))}
        </div>

        {/* Lanes, one per region */}
        <div className="relative">
          {/* Gridlines run the full height behind every lane. */}
          <div
            className="absolute inset-0 pointer-events-none"
            style={{ marginLeft: LANE_LABEL_WIDTH }}
            aria-hidden="true"
          >
            {runWindows.map((window, i) =>
              i === 0 ? null : (
                <span
                  key={window}
                  className="absolute top-0 bottom-0"
                  style={{
                    left: `${positionFor(window, runWindows)}%`,
                    width: 1,
                    background: 'var(--border-subtle)',
                  }}
                />
              ),
            )}
            {nowPercent !== null && (
              <span
                className="absolute top-0 bottom-0"
                title={`now ${stats.now}`}
                style={{
                  left: `${nowPercent}%`,
                  width: 1,
                  background: 'var(--clr-blue)',
                  opacity: 0.5,
                }}
              />
            )}
          </div>

          <div className="relative flex flex-col gap-1.5">
            {regions.map(({ region, recs }) => (
              <Lane
                key={region}
                region={region}
                recs={recs}
                runWindows={runWindows}
                selectedRecId={selectedRecId}
                onSelectRec={onSelectRec}
              />
            ))}
          </div>
        </div>
      </div>
    </section>
  );
}

function Lane({ region, recs, runWindows, selectedRecId, onSelectRec }) {
  // Recs sharing a window sit side by side rather than on top of each other,
  // so each one is offset by the count already placed at that time.
  const placed = new Map();

  return (
    <div className="flex items-center">
      <div style={{ width: LANE_LABEL_WIDTH }} className="pr-2 shrink-0">
        <span
          className="pill w-full text-center font-semibold block"
          style={REGION_STYLE[region]}
        >
          {region}
        </span>
      </div>

      <div
        className="relative flex-1 rounded-lg"
        style={{ height: 26, background: 'var(--bg-muted)' }}
      >
        {recs.map((rec) => {
          const seen = placed.get(rec.scheduled) ?? 0;
          placed.set(rec.scheduled, seen + 1);
          return (
            <RecChip
              key={rec.rec_id}
              rec={rec}
              left={positionFor(rec.scheduled, runWindows)}
              stackIndex={seen}
              selected={rec.rec_id === selectedRecId}
              onSelect={() => onSelectRec(rec.rec_id)}
            />
          );
        })}
      </div>
    </div>
  );
}

function RecChip({ rec, left, stackIndex, selected, onSelect }) {
  return (
    <button
      type="button"
      onClick={onSelect}
      aria-pressed={selected}
      title={`${rec.name} — ${rec.scheduled} IST · ${rec.books_open}/${rec.books_total} open`}
      className="pill absolute flex items-center gap-1.5 transition whitespace-nowrap"
      style={{
        left: `calc(${left}% + ${stackIndex * 8}px)`,
        top: '50%',
        transform: `translateY(-50%) translateX(${stackIndex * 100}%)`,
        background: selected ? 'var(--bg-active)' : 'var(--bg-card-solid)',
        border: `1px solid ${selected ? 'var(--clr-amber)' : 'var(--border-subtle)'}`,
        color: 'var(--text-secondary)',
        boxShadow: selected ? '0 0 0 2px var(--clr-amber-bg)' : 'none',
        zIndex: selected ? 2 : 1,
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
      <span>{shortName(rec.name)}</span>
      <span style={{ color: 'var(--text-muted)' }}>
        {rec.books_open}/{rec.books_total}
      </span>
    </button>
  );
}
