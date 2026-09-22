import {
  ActivityIcon,
  AlertIcon,
  CheckIcon,
  ClockIcon,
  SendIcon,
  UnlockIcon,
} from '@/components/fobo/icons';

const TONE = {
  green: 'var(--clr-green)',
  blue: 'var(--clr-blue)',
  red: 'var(--clr-red)',
  amber: 'var(--clr-amber)',
};

const GLYPH = {
  notified: SendIcon,
  unlocked: UnlockIcon,
  cleared: CheckIcon,
  blocked: AlertIcon,
  analysing: ActivityIcon,
  awaiting: ClockIcon,
};

export default function ActivityFeed({ events }) {
  return (
    <section className="glass-card p-3 flex flex-col gap-2">
      <h2
        className="text-xs font-bold tracking-wide"
        style={{
          color: 'var(--text-primary)',
          fontFamily: 'var(--font-manrope), sans-serif',
        }}
      >
        Notification Activity
      </h2>

      {events.length === 0 && (
        <p className="text-xs" style={{ color: 'var(--text-muted)' }}>
          No activity recorded today.
        </p>
      )}

      <ul className="flex flex-col gap-2">
        {events.map((e, i) => (
          <li key={`${e.at}-${i}`} className="flex items-start gap-2">
            <span
              aria-hidden="true"
              className="flex items-center justify-center rounded-full shrink-0 mt-0.5"
              style={{
                width: 18,
                height: 18,
                background: 'var(--bg-muted)',
                color: TONE[e.tone],
              }}
            >
              {(() => {
                const Glyph = GLYPH[e.kind];
                return Glyph ? <Glyph /> : null;
              })()}
            </span>
            <div className="min-w-0">
              <div
                className="text-[11px]"
                style={{
                  color: 'var(--text-muted)',
                  fontFamily: 'var(--font-mono), monospace',
                }}
              >
                {e.at} IST
              </div>
              <div
                className="text-xs leading-snug"
                style={{ color: 'var(--text-secondary)' }}
              >
                {e.text}
              </div>
            </div>
          </li>
        ))}
      </ul>
    </section>
  );
}
