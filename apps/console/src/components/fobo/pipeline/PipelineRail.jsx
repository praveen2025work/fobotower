const SEGMENTS = [
  { key: 'auto_posted', label: 'auto-posted', color: 'var(--bar-auto)' },
  {
    key: 'awaiting_signoff',
    label: 'awaiting sign-off',
    color: 'var(--bar-awaiting)',
  },
  { key: 'not_open', label: 'not open yet', color: 'var(--bar-notopen)' },
];

const STATE_STYLE = {
  complete: {
    background: 'var(--clr-green-bg)',
    color: 'var(--clr-green)',
    border: '1px solid var(--clr-green)',
  },
  active: {
    background: 'var(--clr-blue-bg)',
    color: 'var(--clr-blue)',
    border: '2px solid var(--clr-blue)',
  },
  pending: {
    background: 'var(--bg-muted)',
    color: 'var(--text-muted)',
    border: '1px dashed var(--border)',
  },
};

/**
 * An unrecognised currentStage yields index -1, which leaves every stage
 * pending. That is the honest rendering: we do not know where the run is,
 * so we do not claim anything is done.
 */
function stageState(stages, currentStage, index) {
  const currentIndex = stages.findIndex((s) => s.key === currentStage);
  if (currentIndex === -1) return 'pending';
  if (index < currentIndex) return 'complete';
  if (index === currentIndex) return 'active';
  return 'pending';
}

export default function PipelineRail({ stages, currentStage, counts }) {
  const total = SEGMENTS.reduce((sum, s) => sum + (counts[s.key] ?? 0), 0);

  return (
    <section className="flex flex-col gap-3">
      <ol className="flex items-start gap-1">
        {stages.map((stage, i) => {
          const state = stageState(stages, currentStage, i);
          return (
            <li
              key={stage.key}
              className="flex-1 flex flex-col items-center gap-1.5"
            >
              <div className="flex items-center w-full">
                <span
                  className="h-px flex-1"
                  style={{
                    background: i === 0 ? 'transparent' : 'var(--border)',
                  }}
                />
                <span
                  aria-label={`${stage.label}: ${state}`}
                  className="flex items-center justify-center rounded-full shrink-0 text-sm font-semibold"
                  style={{ width: 34, height: 34, ...STATE_STYLE[state] }}
                >
                  {state === 'complete' ? '✓' : i + 1}
                </span>
                <span
                  className="h-px flex-1"
                  style={{
                    background:
                      i === stages.length - 1 ? 'transparent' : 'var(--border)',
                  }}
                />
              </div>
              <span
                className="text-xs font-medium text-center leading-tight"
                style={{ color: 'var(--text-primary)' }}
              >
                {stage.label}
              </span>
              <span
                className="text-[11px] text-center leading-tight"
                style={{ color: 'var(--text-muted)' }}
              >
                {stage.sub}
              </span>
            </li>
          );
        })}
      </ol>

      <div
        className="flex h-2 rounded-full overflow-hidden"
        style={{ background: 'var(--bar-notopen)' }}
      >
        {SEGMENTS.map((seg) => {
          const value = counts[seg.key] ?? 0;
          if (total === 0 || value === 0) return null;
          return (
            <div
              key={seg.key}
              style={{
                width: `${(value / total) * 100}%`,
                background: seg.color,
              }}
            />
          );
        })}
      </div>

      <ul aria-label="Book status" className="flex flex-wrap gap-4 text-xs">
        {SEGMENTS.map((seg) => (
          <li key={seg.key} className="flex items-center gap-1.5">
            <span
              aria-hidden="true"
              style={{
                width: 7,
                height: 7,
                borderRadius: '50%',
                background: seg.color,
              }}
            />
            <strong style={{ color: 'var(--text-primary)' }}>
              {counts[seg.key] ?? 0}
            </strong>
            <span style={{ color: 'var(--text-muted)' }}>{seg.label}</span>
          </li>
        ))}
      </ul>
    </section>
  );
}
