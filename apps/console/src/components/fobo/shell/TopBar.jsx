'use client';

const TABS = [
  { key: 'pipeline', label: 'Pipeline' },
  { key: 'analytics', label: 'Agent Analytics' },
];

function formatDate(iso) {
  const parsed = new Date(`${iso}T00:00:00Z`);
  return parsed.toLocaleDateString('en-GB', {
    day: '2-digit',
    month: 'short',
    year: 'numeric',
    timeZone: 'UTC',
  });
}

export default function TopBar({ stats, activeTab, onTabChange }) {
  return (
    <header
      className="flex items-center gap-5 px-6 py-3"
      style={{ background: 'var(--header-grad)', color: 'var(--text-on-brand)' }}
    >
      <div className="min-w-0">
        <h1
          className="text-lg font-bold leading-tight truncate"
          style={{ fontFamily: 'var(--font-manrope), system-ui, sans-serif' }}
        >
          FOBO Control Tower
        </h1>
        <p className="text-xs truncate" style={{ color: 'var(--text-on-brand2)' }}>
          Agent One · horizontal FOBO service across 280 P&amp;Ls
        </p>
      </div>

      <span
        className="pill flex items-center gap-2 shrink-0"
        style={{ background: 'rgba(255,255,255,0.10)' }}
      >
        {formatDate(stats.business_date)}
        <span style={{ color: 'var(--text-on-brand2)' }}>{stats.timezone}</span>
      </span>

      <nav className="flex items-center gap-1">
        {TABS.map((tab) => {
          const active = tab.key === activeTab;
          return (
            <button
              key={tab.key}
              type="button"
              aria-current={active ? 'page' : undefined}
              onClick={() => onTabChange(tab.key)}
              className="pill transition"
              style={{
                background: active ? 'rgba(255,255,255,0.16)' : 'transparent',
                color: 'var(--text-on-brand)',
              }}
            >
              {tab.label}
            </button>
          );
        })}
      </nav>

      <span
        className="pill ml-auto shrink-0 flex items-center gap-1.5"
        style={{ background: 'rgba(255,255,255,0.10)' }}
      >
        <span style={{ color: 'var(--text-on-brand2)' }}>Next run</span>
        <strong>
          {stats.next_run} {stats.timezone}
        </strong>
      </span>

      <div className="flex items-center gap-2 shrink-0">
        <div className="text-right leading-tight">
          <div className="text-sm font-semibold">Praveen</div>
          <div className="text-xs" style={{ color: 'var(--text-on-brand2)' }}>
            FOBO Controller · APAC
          </div>
        </div>
        <span
          className="flex items-center justify-center rounded-full text-sm font-semibold"
          style={{
            width: 32,
            height: 32,
            background: 'var(--barcl-eagle)',
            color: 'var(--barcl-navy)',
          }}
        >
          P
        </span>
      </div>
    </header>
  );
}
