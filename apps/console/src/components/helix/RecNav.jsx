import { useState, useEffect, useRef } from 'react';
import {
  ChevronDown,
  ChevronRight,
  PanelLeftClose as PanelClose,
  PanelLeftOpen as PanelOpen,
  Pin,
  PinOff,
  Search,
  UserCheck,
} from 'lucide-react';
import { FolderTree } from './ui/icons';
import { GROUPS, STATUS, eventLabel } from './constants';
import { bookCounts, manrope } from './lib/format';
import { BookBar } from './ui/BookBar';
import { useRecs } from './data/RecsContext';

export function RecNav({
  collapsed,
  onToggleCollapse,
  pinned,
  onTogglePin,
  selectedId,
  onSelect,
  pendingCount,
  statusOf,
}) {
  const RECS = useRecs();
  const [open, setOpen] = useState(
    Object.fromEntries(GROUPS.map((gp) => [gp.key, true])),
  );
  const [q, setQ] = useState('');
  const pendingIn = (r) =>
    r.adjustments.filter((a) => statusOf(a) === 'Pending').length;
  const tree = GROUPS.map((gp) => ({
    gp,
    recs: RECS.filter(
      (r) =>
        r.group === gp.key &&
        `${r.l4} ${r.name} ${r.id}`.toLowerCase().includes(q.toLowerCase()),
    ),
  })).filter((x) => !q || x.recs.length);
  const pick = (id) => {
    onSelect(id);
    if (!pinned) onToggleCollapse();
  };
  const [fly, setFly] = useState(null);
  const flyRef = useRef(null);
  useEffect(() => {
    if (!fly) return;
    const onDown = (e) => {
      if (
        flyRef.current &&
        !flyRef.current.contains(e.target) &&
        !e.target.closest('[data-group-btn]')
      )
        setFly(null);
    };
    const onKey = (e) => e.key === 'Escape' && setFly(null);
    window.addEventListener('mousedown', onDown);
    window.addEventListener('keydown', onKey);
    return () => {
      window.removeEventListener('mousedown', onDown);
      window.removeEventListener('keydown', onKey);
    };
  }, [fly]);
  useEffect(() => {
    if (!collapsed) setFly(null);
  }, [collapsed]);
  const openFly = (key, e) => {
    const top = e.currentTarget.offsetTop;
    setFly((f) =>
      f && f.key === key
        ? null
        : {
            key,
            top,
          },
    );
  };
  if (collapsed) {
    const fg = fly && GROUPS.find((x) => x.key === fly.key);
    const flyRecs = fg ? RECS.filter((r) => r.group === fg.key) : [];
    return (
      <div
        className={`glass w-14 shrink-0 flex flex-col items-center py-3 gap-3 relative ${fg ? 'z-30' : ''}`}
      >
        <button
          onClick={onToggleCollapse}
          className="hover:opacity-70"
          aria-label="Expand nav"
          title="Expand rec groups"
          style={{
            color: 'var(--text-muted)',
          }}
        >
          <PanelOpen size={18} />
        </button>
        {pendingCount > 0 && (
          <div
            className="relative"
            title={`${pendingCount} adjustments pending sign-off`}
          >
            <UserCheck
              size={16}
              style={{
                color: 'var(--clr-amber)',
              }}
            />
            <span
              className="absolute -top-1.5 -right-2 text-white text-[9px] rounded-full min-w-[14px] h-3.5 px-0.5 flex items-center justify-center"
              style={{
                background: 'var(--clr-red)',
              }}
            >
              {pendingCount}
            </span>
          </div>
        )}
        <div
          className="w-6 h-px"
          style={{
            background: 'var(--border-subtle)',
          }}
        />
        {GROUPS.map((gp) => {
          const recs = RECS.filter((r) => r.group === gp.key);
          const pend = recs.reduce((s, r) => s + pendingIn(r), 0);
          const hasSel = recs.some((r) => r.id === selectedId);
          const isOpen = fly && fly.key === gp.key;
          return (
            <button
              key={gp.key}
              data-group-btn={true}
              onClick={(e) => openFly(gp.key, e)}
              title={`${gp.label}: ${recs.length} recs`}
              aria-label={`Open ${gp.label}`}
              aria-haspopup="menu"
              aria-expanded={!!isOpen}
              className="relative w-9 h-9 rounded-xl flex items-center justify-center transition-shadow"
              style={{
                backgroundColor: gp.bg,
                color: gp.text,
                boxShadow: isOpen || hasSel ? `0 0 0 2px ${gp.text}` : 'none',
              }}
            >
              <FolderTree size={15} />
              {pend > 0 && (
                <span
                  className="absolute -top-1.5 -right-1.5 text-[9px] font-semibold rounded-full min-w-[14px] h-3.5 px-0.5 flex items-center justify-center"
                  style={{
                    background: 'var(--clr-amber)',
                    color: '#fff',
                  }}
                >
                  {pend}
                </span>
              )}
            </button>
          );
        })}
        {fg && (
          <div
            ref={flyRef}
            role="menu"
            aria-label={fg.label}
            className="absolute z-40 w-72 rounded-xl overflow-hidden"
            style={{
              top: fly.top,
              left: 'calc(100% + 10px)',
              background: 'var(--bg-card-solid)',
              border: '1px solid var(--border)',
              boxShadow: 'var(--card-shadow-md)',
            }}
          >
            <div
              className="flex items-center gap-2 px-3 py-2.5"
              style={{
                borderBottom: '1px solid var(--border-subtle)',
                background: 'var(--bg-muted)',
              }}
            >
              <span
                className="w-5 h-5 rounded-md flex items-center justify-center shrink-0"
                style={{
                  backgroundColor: fg.bg,
                  color: fg.text,
                }}
              >
                <FolderTree size={11} />
              </span>
              <span
                className="text-xs font-bold truncate flex-1"
                style={{
                  ...manrope,
                  color: 'var(--text-primary)',
                }}
              >
                {fg.label}
              </span>
              <span
                className="text-[10px] rounded-full px-1.5 py-0.5"
                style={{
                  background: 'var(--bg-card-solid)',
                  color: 'var(--text-muted)',
                }}
              >
                {flyRecs.length}
              </span>
            </div>
            <div className="p-1.5 max-h-[300px] overflow-y-auto">
              {flyRecs.map((r) => {
                const st = STATUS[r.status],
                  active = r.id === selectedId,
                  p = pendingIn(r),
                  c = bookCounts(r.bookStats);
                return (
                  <button
                    key={r.id}
                    role="menuitem"
                    onClick={() => {
                      onSelect(r.id);
                      setFly(null);
                    }}
                    className="w-full text-left px-2.5 py-2 rounded-lg min-w-0 hover:opacity-80"
                    style={
                      active
                        ? {
                            backgroundColor: 'var(--bg-active)',
                          }
                        : {}
                    }
                    aria-current={active ? 'true' : undefined}
                  >
                    <div className="flex items-center gap-1.5 min-w-0">
                      <span
                        className="w-1.5 h-1.5 rounded-full shrink-0"
                        style={{
                          backgroundColor: st.dot,
                        }}
                      />
                      <span
                        className="text-xs truncate flex-1"
                        style={{
                          color: 'var(--text-primary)',
                          fontWeight: active ? 700 : 500,
                        }}
                      >
                        {r.l4}
                      </span>
                      {p > 0 && (
                        <span
                          className="text-[10px] font-semibold shrink-0 rounded-full px-1.5"
                          style={{
                            background: 'var(--clr-amber-bg)',
                            color: 'var(--clr-amber)',
                          }}
                        >
                          {p}
                        </span>
                      )}
                      <span
                        className="text-[10px] shrink-0"
                        style={{
                          color: st.text,
                        }}
                      >
                        {r.status}
                      </span>
                    </div>
                    <div
                      className="text-[10px] ml-3 truncate"
                      style={{
                        color: 'var(--text-muted)',
                      }}
                    >
                      {r.id}
                      {' · '}
                      {eventLabel(r)}
                      {' · '}
                      {c.open}/{c.needsAnalysis}
                      {' open'}
                    </div>
                    <div className="ml-3 mt-1">
                      <BookBar b={r.bookStats} height="h-1" rounded={false} />
                    </div>
                  </button>
                );
              })}
            </div>
            <button
              onClick={() => {
                setFly(null);
                onToggleCollapse();
              }}
              className="w-full flex items-center justify-center gap-1.5 text-[11px] font-semibold py-2 hover:opacity-80"
              style={{
                borderTop: '1px solid var(--border-subtle)',
                color: 'var(--barcl-eagle)',
              }}
            >
              <PanelOpen size={12} />
              {' Expand rec groups panel'}
            </button>
          </div>
        )}
      </div>
    );
  }
  return (
    <div className="glass w-60 shrink-0 flex flex-col min-h-0">
      <div className="flex items-center gap-1.5 px-3 pt-3 pb-2 shrink-0">
        <span
          className="text-xs font-bold flex-1 truncate"
          style={{
            color: 'var(--text-muted)',
          }}
        >
          Rec groups
        </span>
        <button
          onClick={onTogglePin}
          title={
            pinned
              ? 'Unpin: closes on rec select'
              : 'Pin: stays open on rec select'
          }
          className="p-1 rounded hover:opacity-70"
          style={{
            color: pinned ? 'var(--barcl-eagle)' : 'var(--text-muted)',
            background: pinned ? 'var(--clr-blue-bg)' : 'transparent',
          }}
          aria-label={pinned ? 'Unpin nav' : 'Pin nav'}
        >
          {pinned ? <Pin size={13} /> : <PinOff size={13} />}
        </button>
        <button
          onClick={onToggleCollapse}
          className="p-1 rounded hover:opacity-70"
          style={{
            color: 'var(--text-muted)',
          }}
          aria-label="Collapse nav"
        >
          <PanelClose size={14} />
        </button>
      </div>
      <div className="px-3 pb-2 shrink-0">
        <div className="relative">
          <Search
            size={12}
            className="absolute left-2.5 top-1/2 -translate-y-1/2"
            style={{
              color: 'var(--text-muted)',
            }}
          />
          <input
            value={q}
            onChange={(e) => setQ(e.target.value)}
            placeholder="Search L4 or rec id"
            className="w-full pl-7 pr-2 py-1.5 text-xs focus:outline-none"
            style={{
              borderRadius: 'var(--radius-sm)',
              border: '1px solid var(--border)',
              background: 'var(--bg-muted)',
              color: 'var(--text-primary)',
            }}
          />
        </div>
      </div>
      <div className="flex-1 min-h-0 overflow-y-auto px-2 pb-3">
        {tree.map(({ gp, recs }) => {
          const isOpen = open[gp.key];
          const pend = recs.reduce((s, r) => s + pendingIn(r), 0);
          return (
            <div key={gp.key} className="mb-1">
              <button
                onClick={() =>
                  setOpen((o) => ({
                    ...o,
                    [gp.key]: !o[gp.key],
                  }))
                }
                className="w-full flex items-center gap-2 px-2 py-1.5 rounded-lg min-w-0 hover:opacity-80"
                aria-expanded={isOpen}
              >
                {isOpen ? (
                  <ChevronDown
                    size={13}
                    className="shrink-0"
                    style={{
                      color: 'var(--text-muted)',
                    }}
                  />
                ) : (
                  <ChevronRight
                    size={13}
                    className="shrink-0"
                    style={{
                      color: 'var(--text-muted)',
                    }}
                  />
                )}
                <span
                  className="w-5 h-5 rounded-md flex items-center justify-center shrink-0"
                  style={{
                    backgroundColor: gp.bg,
                    color: gp.text,
                  }}
                >
                  <FolderTree size={11} />
                </span>
                <span
                  className="text-xs font-semibold flex-1 text-left truncate"
                  style={{
                    color: 'var(--text-primary)',
                  }}
                  title={gp.label}
                >
                  {gp.label}
                </span>
                {pend > 0 && (
                  <span
                    className="text-[10px] font-semibold rounded-full px-1.5 py-0.5 shrink-0"
                    style={{
                      background: 'var(--clr-amber-bg)',
                      color: 'var(--clr-amber)',
                    }}
                  >
                    {pend}
                  </span>
                )}
                <span
                  className="text-[10px] rounded-full px-1.5 py-0.5 shrink-0"
                  style={{
                    background: 'var(--bg-muted)',
                    color: 'var(--text-muted)',
                  }}
                >
                  {recs.length}
                </span>
              </button>
              {isOpen && (
                <div
                  className="ml-4 pl-2"
                  style={{
                    borderLeft: '1px solid var(--border-subtle)',
                  }}
                >
                  {recs.map((r) => {
                    const st = STATUS[r.status],
                      active = r.id === selectedId,
                      p = pendingIn(r),
                      c = bookCounts(r.bookStats);
                    return (
                      <button
                        key={r.id}
                        onClick={() => pick(r.id)}
                        className="w-full text-left px-2 py-1.5 rounded-lg mb-0.5 transition-all min-w-0"
                        style={
                          active
                            ? {
                                backgroundColor: 'var(--bg-active)',
                                borderRadius: 'var(--radius-sm)',
                              }
                            : {}
                        }
                        aria-current={active ? 'true' : undefined}
                      >
                        <div className="flex items-center gap-1.5 min-w-0">
                          <span
                            className="w-1.5 h-1.5 rounded-full shrink-0"
                            style={{
                              backgroundColor: st.dot,
                            }}
                          />
                          <span
                            className="text-xs truncate flex-1"
                            style={{
                              color: active
                                ? 'var(--text-primary)'
                                : 'var(--text-secondary)',
                              fontWeight: active ? 700 : 400,
                            }}
                          >
                            {r.l4}
                          </span>
                          {p > 0 && (
                            <span
                              className="text-[10px] font-semibold shrink-0"
                              style={{
                                color: 'var(--clr-amber)',
                              }}
                            >
                              {p}
                            </span>
                          )}
                        </div>
                        <div
                          className="text-[10px] ml-3 truncate"
                          style={{
                            color: 'var(--text-muted)',
                          }}
                        >
                          {r.id}
                          {' · '}
                          {eventLabel(r)}
                          {' · '}
                          {c.open}/{c.needsAnalysis}
                          {' open'}
                        </div>
                        <div className="ml-3 mt-1">
                          <BookBar
                            b={r.bookStats}
                            height="h-1"
                            rounded={false}
                          />
                        </div>
                      </button>
                    );
                  })}
                </div>
              )}
            </div>
          );
        })}
      </div>
    </div>
  );
}
