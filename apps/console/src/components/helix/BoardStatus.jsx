import { manrope } from './lib/format';

/**
 * Shown until the orchestrator has answered. A failed load is not a dead end:
 * it says what the console expected and offers a retry.
 */
export function BoardStatus({ load, onRetry }) {
  const failed = load.state === 'error';
  return (
    <div
      className="min-h-screen flex items-center justify-center p-6"
      style={{ fontFamily: 'var(--hx-font-inter), sans-serif' }}
    >
      <div className="glass p-6 max-w-md w-full">
        <div
          className="text-[15px] font-bold"
          style={{ ...manrope, color: 'var(--text-primary)' }}
        >
          FOBO Control Tower
        </div>
        {failed ? (
          <>
            <p
              className="text-[12.5px] mt-2"
              style={{ color: 'var(--clr-red)' }}
            >
              {load.error}
            </p>
            <p
              className="text-[11.5px] mt-2"
              style={{ color: 'var(--text-muted)' }}
            >
              The console reads from the orchestrator API on{' '}
              <code>http://localhost:8100</code>. Start it from{' '}
              <code>apps/api</code> with{' '}
              <code>uvicorn api.main:app --port 8100</code>.
            </p>
            <button
              type="button"
              onClick={onRetry}
              className="pill mt-4"
              style={{
                background: 'var(--clr-blue-bg)',
                color: 'var(--clr-blue)',
                border: '1px solid var(--clr-blue)',
              }}
            >
              Retry
            </button>
          </>
        ) : (
          <p
            className="text-[12.5px] mt-2"
            style={{ color: 'var(--text-muted)' }}
          >
            Loading recs and opening their Helix sessions…
          </p>
        )}
      </div>
    </div>
  );
}
