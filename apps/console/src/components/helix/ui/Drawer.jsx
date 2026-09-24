import { useEffect } from 'react';
import { X as XIcon } from 'lucide-react';
import { manrope } from '../lib/format';

export function Drawer({ title, subtitle, width = 640, onClose, children }) {
  useEffect(() => {
    const k = (e) => e.key === 'Escape' && onClose();
    window.addEventListener('keydown', k);
    return () => window.removeEventListener('keydown', k);
  }, [onClose]);
  return (
    <div
      className="fixed inset-0 z-40 flex justify-end"
      style={{
        backdropFilter: 'blur(2px)',
        background: 'rgba(0,20,50,0.35)',
      }}
    >
      <button className="flex-1" onClick={onClose} aria-label="Close drawer" />
      <div
        className="flex flex-col h-full overflow-hidden"
        style={{
          width,
          maxWidth: '100vw',
          background: 'var(--bg-card-solid)',
          borderLeft: '1px solid var(--border)',
          boxShadow: 'var(--card-shadow-md)',
        }}
      >
        <div
          className="flex items-start justify-between px-5 py-4 shrink-0"
          style={{
            borderBottom: '1px solid var(--border)',
            background: 'var(--bg-muted)',
          }}
        >
          <div className="min-w-0">
            <div
              className="text-[15px] font-bold truncate"
              style={{
                ...manrope,
                color: 'var(--text-primary)',
              }}
            >
              {title}
            </div>
            {subtitle && (
              <div
                className="text-[11px] mt-0.5 truncate"
                style={{
                  color: 'var(--text-muted)',
                }}
              >
                {subtitle}
              </div>
            )}
          </div>
          <button
            onClick={onClose}
            className="ml-3 shrink-0 p-1.5 rounded-lg hover:opacity-70"
            style={{
              background: 'var(--bg-hover)',
              color: 'var(--text-secondary)',
            }}
            aria-label="Close"
          >
            <XIcon size={15} />
          </button>
        </div>
        <div className="flex-1 overflow-y-auto px-5 py-4">{children}</div>
      </div>
    </div>
  );
}
