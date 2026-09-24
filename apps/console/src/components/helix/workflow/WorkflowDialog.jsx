import { useEffect } from 'react';
import { manrope } from '../lib/format';

/** A confirm dialog styled like the adjustments ConfirmDialog. */
export function WorkflowDialog({ title, confirmLabel, ready, busy, error, onCancel, onConfirm, children }) {
  useEffect(() => {
    const k = (e) => e.key === 'Escape' && onCancel();
    window.addEventListener('keydown', k);
    return () => window.removeEventListener('keydown', k);
  }, [onCancel]);
  return (
    <div
      className="fixed inset-0 z-50 flex items-center justify-center p-4"
      style={{ background: 'rgba(0,20,50,0.45)', backdropFilter: 'blur(2px)' }}
      role="dialog"
      aria-modal="true"
      aria-labelledby="workflow-dialog-title"
    >
      <div
        className="w-full max-w-[480px] rounded-2xl overflow-hidden"
        style={{ background: 'var(--bg-card-solid)', border: '1px solid var(--border)', boxShadow: 'var(--card-shadow-md)' }}
      >
        <div
          id="workflow-dialog-title"
          className="px-5 py-4 text-[15px] font-bold"
          style={{ ...manrope, color: 'var(--text-primary)', borderBottom: '1px solid var(--border)' }}
        >
          {title}
        </div>
        <div className="px-5 py-4 flex flex-col gap-2">
          {children}
          {error && (
            <div role="alert" className="text-[12px]" style={{ color: 'var(--clr-red)' }}>
              {error}
            </div>
          )}
        </div>
        <div className="px-5 py-3 flex justify-end gap-2" style={{ borderTop: '1px solid var(--border)' }}>
          <button
            type="button"
            onClick={onCancel}
            className="text-[12px] px-3 py-1.5 rounded-full"
            style={{ border: '1px solid var(--border)', color: 'var(--text-secondary)' }}
          >
            Cancel
          </button>
          <button
            type="button"
            disabled={!ready || busy}
            onClick={onConfirm}
            className="text-[12px] font-semibold px-4 py-1.5 rounded-full disabled:opacity-40"
            style={{ background: 'var(--clr-blue)', color: 'var(--text-on-brand)' }}
          >
            {busy ? 'Working…' : confirmLabel}
          </button>
        </div>
      </div>
    </div>
  );
}

export function Check({ checked, onChange, children }) {
  return (
    <label
      className="flex items-start gap-2 text-[12px] rounded-lg px-2.5 py-2 cursor-pointer"
      style={{ background: 'var(--bg-muted)', color: 'var(--text-secondary)' }}
    >
      <input type="checkbox" className="mt-0.5" checked={checked} onChange={(e) => onChange(e.target.checked)} />
      <span>{children}</span>
    </label>
  );
}
