import { useState, useEffect, useRef } from 'react';
import { BellRing as Bell, X as XIcon } from 'lucide-react';
import { ACTIVITY_STYLE } from './constants';
import { manrope, mono } from './lib/format';
import { useRecs } from './data/RecsContext';

export function NotificationBell({ activity, onSelectRec }) {
  const RECS = useRecs();
  const [open, setOpen] = useState(false);
  const [seen, setSeen] = useState(Math.max(0, activity.length - 2));
  const ref = useRef(null);
  const unread = Math.max(0, activity.length - seen);
  useEffect(() => {
    if (!open) return;
    setSeen(activity.length);
    const onDown = (e) =>
      ref.current && !ref.current.contains(e.target) && setOpen(false);
    const onKey = (e) => e.key === 'Escape' && setOpen(false);
    window.addEventListener('mousedown', onDown);
    window.addEventListener('keydown', onKey);
    return () => {
      window.removeEventListener('mousedown', onDown);
      window.removeEventListener('keydown', onKey);
    };
  }, [open, activity.length]);
  return (
    <div ref={ref} className="relative">
      <button
        onClick={() => setOpen((o) => !o)}
        className="relative w-8 h-8 rounded-full flex items-center justify-center hover:opacity-80"
        style={{
          backgroundColor: open
            ? 'rgba(255,255,255,0.18)'
            : 'var(--bg-header-deep)',
          color: 'var(--text-on-brand2)',
        }}
        aria-label={`Notification activity${unread ? `, ${unread} new` : ''}`}
        aria-haspopup="dialog"
        aria-expanded={open}
        title="Notification activity"
      >
        <Bell size={15} />
        {unread > 0 && (
          <span
            className="absolute -top-1 -right-1 text-white text-[9px] font-semibold rounded-full min-w-[15px] h-[15px] px-1 flex items-center justify-center"
            style={{
              background: 'var(--clr-red)',
              boxShadow: '0 0 0 2px var(--bg-header)',
            }}
          >
            {unread}
          </span>
        )}
      </button>
      {open && (
        <div
          role="dialog"
          aria-label="Notification activity"
          className="absolute right-0 top-full mt-2 w-[360px] max-w-[calc(100vw-24px)] rounded-xl overflow-hidden flex flex-col"
          style={{
            maxHeight: '70vh',
            background: 'var(--bg-card-solid)',
            border: '1px solid var(--border)',
            boxShadow: 'var(--card-shadow-md)',
          }}
        >
          <div
            className="flex items-center gap-2 px-3.5 py-2.5 shrink-0"
            style={{
              borderBottom: '1px solid var(--border-subtle)',
              background: 'var(--bg-muted)',
            }}
          >
            <Bell
              size={13}
              style={{
                color: 'var(--barcl-eagle)',
              }}
            />
            <span
              className="text-xs font-bold flex-1"
              style={{
                ...manrope,
                color: 'var(--text-primary)',
              }}
            >
              Notification Activity
            </span>
            <span
              className="text-[10.5px]"
              style={{
                color: 'var(--text-muted)',
              }}
            >
              {activity.length}
              {' events today'}
            </span>
            <button
              onClick={() => setOpen(false)}
              className="p-1 rounded hover:opacity-70"
              style={{
                color: 'var(--text-muted)',
              }}
              aria-label="Close"
            >
              <XIcon size={13} />
            </button>
          </div>
          <div className="overflow-y-auto px-3.5 py-3 hx-space-y-2.5">
            {activity.map((e, i) => {
              const st = ACTIVITY_STYLE[e.type],
                Icon = st.icon;
              const rec = RECS.find((r) => r.id === e.recId);
              return (
                <button
                  key={i}
                  onClick={() => {
                    onSelectRec(e.recId);
                    setOpen(false);
                  }}
                  className="w-full flex gap-2.5 min-w-0 text-left rounded-lg hover:opacity-80"
                >
                  <div className="flex flex-col items-center shrink-0">
                    <div
                      className="w-6 h-6 rounded-full flex items-center justify-center"
                      style={{
                        background: `color-mix(in srgb, var(${st.cssVar}) 14%, transparent)`,
                        border: `1px solid color-mix(in srgb, var(${st.cssVar}) 20%, transparent)`,
                      }}
                    >
                      <Icon
                        size={12}
                        style={{
                          color: `var(${st.cssVar})`,
                        }}
                      />
                    </div>
                    {i < activity.length - 1 && (
                      <div
                        className="w-px flex-1 mt-1"
                        style={{
                          background: 'var(--border-subtle)',
                        }}
                      />
                    )}
                  </div>
                  <div className="pb-2 min-w-0">
                    <div
                      className="text-[11px] flex items-center gap-1.5"
                      style={{
                        ...mono,
                        color: 'var(--text-muted)',
                      }}
                    >
                      {e.time}
                      {' IST'}
                      {rec && (
                        <span
                          className="truncate"
                          style={{
                            fontFamily: 'inherit',
                          }}
                        >
                          {'· '}
                          {rec.l4}
                        </span>
                      )}
                    </div>
                    <div
                      className="text-xs leading-snug"
                      style={{
                        color: 'var(--text-secondary)',
                      }}
                    >
                      {e.text}
                    </div>
                  </div>
                </button>
              );
            })}
          </div>
        </div>
      )}
    </div>
  );
}
