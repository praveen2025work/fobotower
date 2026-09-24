import { TONES } from '../constants';
import { mono } from '../lib/format';

export function KvCards({ items }) {
  return (
    <div className="grid grid-cols-3 gap-2 mb-2.5">
      {items.map((r, i) => (
        <div
          key={i}
          className="rounded-lg px-2.5 py-2 min-w-0"
          style={{
            background:
              i === 2 ? 'var(--clr-amber-bg)' : 'var(--bg-card-solid)',
            border: `1px solid ${i === 2 ? 'var(--clr-amber-dot)' : 'var(--border)'}`,
          }}
        >
          <div
            className="text-[10px] font-semibold mb-1"
            style={{
              color: i === 2 ? 'var(--clr-amber)' : 'var(--text-muted)',
            }}
          >
            {r.label}
          </div>
          <div
            className="text-[12px] font-bold tabular-nums leading-tight break-words"
            style={{
              ...mono,
              color: i === 2 ? 'var(--clr-amber)' : 'var(--text-primary)',
            }}
          >
            {r.value}
          </div>
          <div
            className="text-[10px] mt-1 leading-tight"
            style={{
              color: 'var(--text-muted)',
            }}
          >
            {r.note}
          </div>
        </div>
      ))}
    </div>
  );
}

export function Callout({ tone = 'ok', title, text }) {
  const t = TONES[tone],
    Icon = t.icon;
  return (
    <div
      className="flex items-start gap-2 rounded-lg px-2.5 py-2 mb-2.5"
      style={{
        background: t.bg,
      }}
    >
      <Icon
        size={13}
        className="shrink-0 mt-0.5"
        style={{
          color: t.fg,
        }}
      />
      <div className="min-w-0">
        {title && (
          <div
            className="text-[10px] font-semibold mb-0.5"
            style={{
              color: t.fg,
            }}
          >
            {title}
          </div>
        )}
        <p
          className="text-[12px] leading-relaxed"
          style={{
            color: t.fg,
          }}
        >
          {text}
        </p>
      </div>
    </div>
  );
}

export function VerifyList({ items, title = 'Before you approve, verify' }) {
  return (
    <div>
      <div
        className="text-[10px] font-semibold mb-1"
        style={{
          color: 'var(--text-muted)',
        }}
      >
        {title}
      </div>
      <ul className="hx-space-y-1">
        {items.map((r, i) => (
          <li
            key={i}
            className="flex items-start gap-1.5 text-[11px]"
            style={{
              color: 'var(--text-secondary)',
            }}
          >
            <span
              className="shrink-0 mt-1.5 w-1 h-1 rounded-full"
              style={{
                background: 'var(--text-muted)',
              }}
            />
            {r}
          </li>
        ))}
      </ul>
    </div>
  );
}
