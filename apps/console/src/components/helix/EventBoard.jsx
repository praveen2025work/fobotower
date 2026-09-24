import { Fragment } from 'react';
import { Zap } from 'lucide-react';
import { GROUPS, STATUS, eventLabel } from './constants';
import { Stat } from './ui/Kpi';
import { useRecs } from './data/RecsContext';

export function EventBoard({ selectedId, onSelect, stats }) {
  const RECS = useRecs();
  return (
    <div className="px-6 md:px-10 pt-3 shrink-0">
      <div className="glass px-4 py-2">
        <div className="flex items-center gap-x-3 gap-y-1 flex-wrap mb-1.5">
          <Zap
            size={12}
            className="shrink-0"
            style={{
              color: 'var(--barcl-eagle)',
            }}
          />
          <span
            className="text-[11px] font-bold whitespace-nowrap"
            style={{
              color: 'var(--text-secondary)',
            }}
          >
            Event status
          </span>
          <span
            className="text-[11px] whitespace-nowrap"
            style={{
              color: 'var(--text-muted)',
            }}
          >
            Sessions start when Helix receives the One Fin UX Ready event
          </span>
          <div className="ml-auto flex items-center gap-x-3 gap-y-1 flex-wrap text-[11px] tabular-nums">
            <Stat v={stats.total} l="recs" c="var(--barcl-eagle)" />
            <Stat v={stats.waiting} l="awaiting Ready" c="var(--clr-grey)" />
            <Stat v={stats.cleared} l="cleared" c="var(--clr-green)" />
            <Stat
              v={stats.awaiting}
              l="awaiting sign-off"
              c="var(--clr-amber)"
            />
            <Stat v={stats.blocked} l="blocked" c="var(--clr-red)" />
            <Stat v={stats.pending} l="adj. pending" c="var(--clr-purple)" />
            <Stat v={stats.booksAuto} l="auto-posted" c="var(--clr-purple)" />
            <Stat v={stats.booksOpen} l="books open" c="var(--clr-amber-dot)" />
            <Stat
              v={`${stats.booksUnlocked}/${stats.books}`}
              l="unlocked"
              c="var(--clr-blue)"
            />
          </div>
        </div>
        <div
          className="grid gap-x-1.5 gap-y-1 items-center"
          style={{
            gridTemplateColumns: '104px minmax(0,1fr)',
          }}
        >
          {GROUPS.map((gp) => (
            <Fragment key={gp.key}>
              <span
                className="text-[10px] font-bold px-1.5 py-0.5 rounded truncate"
                title={gp.label}
                style={{
                  backgroundColor: gp.bg,
                  color: gp.text,
                }}
              >
                {gp.short}
              </span>
              <div className="flex gap-1 min-w-0">
                {RECS.filter((r) => r.group === gp.key).map((r) => {
                  const st = STATUS[r.status],
                    sel = r.id === selectedId;
                  return (
                    <button
                      key={r.id}
                      onClick={() => onSelect(r.id)}
                      title={`${r.name}: ${r.status}${r.eventId ? ` (${r.eventId})` : `, MB Rec ready ${r.mb.available}/${r.mb.total}`}`}
                      className="flex-1 min-w-0 h-6 rounded px-1.5 flex items-center gap-1 border"
                      style={{
                        backgroundColor: st.bg,
                        borderColor: sel
                          ? 'var(--text-primary)'
                          : 'transparent',
                      }}
                    >
                      <span
                        className="w-1.5 h-1.5 rounded-full shrink-0"
                        style={{
                          backgroundColor: st.dot,
                        }}
                      />
                      <span
                        className="text-[10px] truncate"
                        style={{
                          color: st.text,
                        }}
                      >
                        {r.l4}
                      </span>
                      <span
                        className="ml-auto text-[10px] tabular-nums shrink-0 opacity-75 flex items-center gap-0.5"
                        style={{
                          color: st.text,
                        }}
                      >
                        {r.readyAt && <Zap size={9} />}
                        {eventLabel(r)}
                      </span>
                    </button>
                  );
                })}
              </div>
            </Fragment>
          ))}
        </div>
      </div>
    </div>
  );
}
