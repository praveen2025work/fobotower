import { setDevCaller } from '@/lib/apiClient';

/** Dev only: act as another caller, so a second person can approve a draft. */
export function DevCallerSwitch({ callers, current, onSwitch }) {
  if (!callers?.length) return null;
  return (
    <label className="flex items-center gap-1 text-[10px]" style={{ color: 'var(--text-on-brand2)' }}>
      Act as
      <select
        aria-label="Act as"
        value={current || ''}
        onChange={(e) => {
          setDevCaller(e.target.value);
          onSwitch(e.target.value);
        }}
        className="text-[11px] rounded px-1 py-0.5"
        style={{ background: 'var(--bg-header-deep)', color: 'var(--text-on-brand)', border: '1px solid rgba(255,255,255,0.2)' }}
      >
        {callers.map((c) => (
          <option key={c.id} value={c.id}>
            {c.id} ({c.roles.join(', ')})
          </option>
        ))}
      </select>
    </label>
  );
}
