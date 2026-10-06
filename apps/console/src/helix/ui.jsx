// Small presentational pieces shared by the Agent One Finance screens.

const TONES = {
  awaiting_review: 'bg-amber-100 text-amber-800',
  completed: 'bg-emerald-100 text-emerald-800',
  escalated: 'bg-rose-100 text-rose-800',
  failed: 'bg-rose-100 text-rose-800',
  running: 'bg-sky-100 text-sky-800',
  proposed: 'bg-sky-100 text-sky-800',
  approve: 'bg-emerald-100 text-emerald-800',
  reject: 'bg-rose-100 text-rose-800',
};

export function StatusPill({ value }) {
  return (
    <span
      className={`inline-block rounded-full px-2 py-0.5 text-xs font-medium ${TONES[value] ?? 'bg-gray-100 text-gray-700'}`}
    >
      {String(value ?? '—').replaceAll('_', ' ')}
    </span>
  );
}

export function Panel({ title, aside, children }) {
  return (
    <section className="rounded-xl border border-gray-200 bg-white p-4">
      {(title || aside) && (
        <header className="mb-3 flex items-center justify-between gap-2">
          {title && <h2 className="text-sm font-semibold text-gray-800">{title}</h2>}
          {aside}
        </header>
      )}
      {children}
    </section>
  );
}

export function Loading({ what }) {
  return <p className="text-sm text-gray-500">Loading {what}…</p>;
}

export function ErrorNote({ error }) {
  return (
    <div role="alert" className="rounded-lg bg-rose-50 p-3 text-sm text-rose-800">
      {error.message}
      {error.problems?.length > 0 && (
        <ul className="mt-1 list-disc pl-5">
          {error.problems.map((p) => (
            <li key={p}>{p}</li>
          ))}
        </ul>
      )}
    </div>
  );
}

export function Empty({ children }) {
  return <p className="text-sm text-gray-500">{children}</p>;
}

export function formatValue(v) {
  if (typeof v === 'number') return v.toLocaleString('en-GB', { maximumFractionDigits: 2 });
  if (v === null || v === undefined) return '—';
  return String(v);
}
