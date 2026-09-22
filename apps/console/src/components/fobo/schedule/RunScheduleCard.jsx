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

function shortName(name) {
  return name.split('—').pop().trim();
}

export default function RunScheduleCard({ stats, regions, runWindows }) {
  return (
    <section className="glass-card p-4">
      <div className="flex items-baseline gap-3 mb-2">
        <h2
          className="text-xs font-bold tracking-wide"
          style={{
            color: 'var(--text-primary)',
            fontFamily: 'Manrope, sans-serif',
          }}
        >
          RUN SCHEDULE — TODAY
        </h2>
        <span className="text-xs" style={{ color: 'var(--text-muted)' }}>
          now {stats.now} {stats.timezone} · next {stats.next_run}
        </span>
      </div>

      <StatChipRow stats={stats} />

      <div
        className="mt-4 grid gap-x-3 gap-y-2 items-center"
        style={{ gridTemplateColumns: `60px repeat(${runWindows.length}, 1fr)` }}
      >
        <div />
        {runWindows.map((window) => (
          <div
            key={window}
            className="text-xs"
            style={{ color: 'var(--text-muted)' }}
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
          />
        ))}
      </div>
    </section>
  );
}

function RegionRow({ region, recs, runWindows }) {
  return (
    <>
      <span
        className="pill text-center font-semibold"
        style={REGION_STYLE[region]}
      >
        {region}
      </span>
      {runWindows.map((window) => (
        <div key={window} className="flex flex-wrap gap-1">
          {recs
            .filter((rec) => rec.scheduled === window)
            .map((rec) => (
              <span
                key={rec.rec_id}
                className="pill flex items-center gap-1.5"
                style={{
                  background: 'var(--bg-muted)',
                  border: '1px solid var(--border-subtle)',
                  color: 'var(--text-secondary)',
                }}
              >
                <span
                  aria-hidden="true"
                  style={{
                    width: 6,
                    height: 6,
                    borderRadius: '50%',
                    background: STATUS_DOT[rec.status],
                  }}
                />
                {shortName(rec.name)}
                <span style={{ color: 'var(--text-muted)' }}>
                  {rec.books_open}/{rec.books_total}
                </span>
              </span>
            ))}
        </div>
      ))}
    </>
  );
}
