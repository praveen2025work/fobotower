import { Sparkles } from 'lucide-react';
import { manrope } from '../lib/format';

export function Kpi({ icon: Icon, label, value, sub, color }) {
  return (
    <div className="glass px-4 py-3 min-w-0">
      <div className="flex items-center gap-1.5 text-[10px] text-slate-400 uppercase tracking-wide min-w-0">
        {Icon && <Icon size={11} className="shrink-0" />}
        <span className="truncate">{label}</span>
      </div>
      <div
        className="text-lg font-extrabold mt-0.5 truncate"
        style={{
          color,
          ...manrope,
        }}
      >
        {value}
      </div>
      {sub && (
        <div className="text-[10px] text-slate-400 mt-0.5 truncate">{sub}</div>
      )}
    </div>
  );
}

export function Stat({ v, l, c }) {
  return (
    <span className="whitespace-nowrap">
      <span
        className="font-extrabold"
        style={{
          color: c,
          ...manrope,
        }}
      >
        {v}
      </span>
      <span
        className="ml-1"
        style={{
          color: 'var(--text-muted)',
        }}
      >
        {l}
      </span>
    </span>
  );
}

export function Label({ children }) {
  return (
    <div
      className="text-[10px] font-semibold mb-0.5"
      style={{
        color: 'var(--text-muted)',
      }}
    >
      {children}
    </div>
  );
}

export function AgentAvatar() {
  return (
    <div
      className="w-6 h-6 rounded-full flex items-center justify-center shrink-0"
      style={{
        background: 'var(--bg-header)',
      }}
    >
      <Sparkles
        size={12}
        style={{
          color: '#fff',
        }}
      />
    </div>
  );
}
