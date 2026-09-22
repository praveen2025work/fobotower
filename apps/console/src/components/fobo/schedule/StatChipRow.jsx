const CHIPS = [
  { key: 'recs', label: 'recs', color: 'var(--text-primary)' },
  { key: 'cleared', label: 'cleared', color: 'var(--clr-green)' },
  { key: 'awaiting', label: 'awaiting', color: 'var(--clr-amber)' },
  { key: 'blocked', label: 'blocked', color: 'var(--clr-red)' },
  { key: 'adj_pending', label: 'adj. pending', color: 'var(--clr-purple)' },
  { key: 'auto_posted', label: 'auto-posted', color: 'var(--clr-green)' },
  { key: 'books_open', label: 'books open', color: 'var(--clr-blue)' },
  { key: 'books_not_open', label: 'not open', color: 'var(--text-muted)' },
];

export default function StatChipRow({ stats }) {
  return (
    <div className="flex flex-wrap items-baseline gap-x-4 gap-y-1 text-xs">
      {CHIPS.map(({ key, label, color }) => (
        <span key={key} className="flex items-baseline gap-1">
          <strong style={{ color }}>{stats[key]}</strong>
          <span style={{ color: 'var(--text-muted)' }}>{label}</span>
        </span>
      ))}
      <span className="flex items-baseline gap-1">
        <strong style={{ color: 'var(--clr-blue)' }}>
          {stats.unlocked}/{stats.unlocked_total}
        </strong>
        <span style={{ color: 'var(--text-muted)' }}>unlocked</span>
      </span>
    </div>
  );
}
