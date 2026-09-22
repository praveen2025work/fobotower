'use client';

/**
 * A transient fetch failure must not be a dead end.
 *
 * The store records the error; this offers a way out of it. Without the
 * retry the page stays stuck on the error branch until a manual refresh,
 * which is a poor answer to a one-second blip.
 */
export default function ConnectionError({ message, onRetry }) {
  return (
    <div className="p-6 flex flex-col items-start gap-3">
      <p className="text-sm" style={{ color: 'var(--clr-red)' }}>
        {message}
      </p>
      <p className="text-xs" style={{ color: 'var(--text-muted)' }}>
        The console expects the investigation API on{' '}
        <code>http://localhost:8100</code>. Start it with{' '}
        <code>uvicorn api.main:app --port 8100</code> from <code>apps/api</code>.
      </p>
      <button
        type="button"
        onClick={onRetry}
        className="pill font-medium"
        style={{
          background: 'var(--clr-blue-bg)',
          color: 'var(--clr-blue)',
          border: '1px solid var(--clr-blue)',
          padding: '5px 14px',
        }}
      >
        Retry
      </button>
    </div>
  );
}
