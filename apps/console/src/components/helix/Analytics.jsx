import { useState, useMemo } from 'react';
import { Gauge, Layers, Terminal, UserCheck, Zap } from 'lucide-react';
import {
  Bar,
  BarChart,
  CartesianGrid,
  Cell,
  Legend,
  Pie,
  PieChart,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from 'recharts';
import { BAR_SEGMENTS, GROUPS } from './constants';
import { groundingRate, manrope } from './lib/format';
import { Kpi } from './ui/Kpi';
import { Chip } from './ui/Pills';
import { useRecs } from './data/RecsContext';

export function Analytics({ statusOf, callCount, hoursSaved }) {
  const RECS = useRecs();
  const [groups, setGroups] = useState(GROUPS.map((gp) => gp.key));
  const toggle = (k) =>
    setGroups((s) => (s.includes(k) ? s.filter((x) => x !== k) : [...s, k]));
  const recs = useMemo(
    () => RECS.filter((r) => groups.includes(r.group)),
    [RECS, groups],
  );
  const byL4 = recs.map((r) => ({
    l4: r.l4,
    ...r.bookStats,
  }));
  const adjs = recs.flatMap((r) => r.adjustments);
  const auto = adjs.filter((a) => a.type === 'Auto').length,
    manual = adjs.length - auto;
  const pie = [
    {
      name: 'Auto',
      value: auto,
    },
    {
      name: 'Manual',
      value: manual,
    },
  ];
  const patterns = new Set(adjs.map((a) => a.pattern)).size;
  const pending = adjs.filter((a) => statusOf(a) === 'Pending').length;
  const pr = recs
    .filter((r) => groundingRate(r) !== null)
    .map((r) => ({
      l4: r.l4,
      passRate: Math.round(groundingRate(r) * 10) / 10,
    }));
  const avg = pr.reduce((s, d) => s + d.passRate, 0) / (pr.length || 1);
  const tip = {
    contentStyle: {
      fontSize: 12,
      borderRadius: 8,
      borderColor: 'var(--border)',
      backgroundColor: 'var(--bg-card)',
      color: 'var(--text-primary)',
    },
  };
  const axis = {
    tick: {
      fontSize: 11,
      fill: 'var(--text-secondary)',
    },
    axisLine: {
      stroke: 'var(--border)',
    },
  };
  return (
    <div>
      <div className="glass px-5 py-4 mb-5">
        <div className="flex flex-wrap items-center gap-x-8 gap-y-3">
          <div className="flex items-center gap-2 flex-wrap">
            <span
              className="text-[11px] font-semibold mr-1"
              style={{
                color: 'var(--text-muted)',
              }}
            >
              Rec group
            </span>
            {GROUPS.map((gp) => (
              <Chip
                key={gp.key}
                active={groups.includes(gp.key)}
                onClick={() => toggle(gp.key)}
              >
                {gp.label}
              </Chip>
            ))}
          </div>
        </div>
      </div>
      <div className="grid grid-cols-2 sm:grid-cols-5 gap-3 mb-6">
        <Kpi
          icon={Gauge}
          label="Grounding pass rate"
          value={`${avg.toFixed(1)}%`}
          sub="completed sessions today"
          color="var(--clr-blue)"
        />
        <Kpi
          icon={Layers}
          label="Decisions saved"
          value={`${adjs.length}→${patterns}`}
          sub="adjustments grouped into patterns"
          color="var(--clr-purple)"
        />
        <Kpi
          icon={UserCheck}
          label="Pending sign-off"
          value={pending}
          sub="need double confirmation"
          color="var(--clr-amber)"
        />
        <Kpi
          icon={Terminal}
          label="MCP calls"
          value={callCount}
          sub="across open sessions"
          color="var(--barcl-eagle)"
        />
        <Kpi
          icon={Zap}
          label="Est. hours saved"
          value={hoursSaved ? `${hoursSaved.value} hrs` : '—'}
          sub={hoursSaved ? hoursSaved.basis : 'today, vs. manual baseline'}
          color="var(--clr-green)"
        />
      </div>
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-4 mb-6">
        <div className="glass p-4">
          <div
            className="text-xs font-bold mb-3"
            style={{
              ...manrope,
              color: 'var(--text-secondary)',
            }}
          >
            Master books by L4 and state
          </div>
          <ResponsiveContainer width="100%" height={220}>
            <BarChart data={byL4} barSize={26}>
              <CartesianGrid
                strokeDasharray="3 3"
                vertical={false}
                stroke="var(--border-subtle)"
              />
              <XAxis
                dataKey="l4"
                {...axis}
                interval={0}
                tick={{
                  fontSize: 10,
                  fill: 'var(--text-secondary)',
                }}
                tickFormatter={(v) =>
                  v === 'Equity Derivatives' ? 'Eq Derivs' : v
                }
              />
              <YAxis allowDecimals={false} {...axis} />
              <Tooltip {...tip} />
              <Legend
                wrapperStyle={{
                  fontSize: 11,
                }}
              />
              {BAR_SEGMENTS.map((s) => (
                <Bar
                  key={s.key}
                  dataKey={s.key}
                  name={s.label}
                  stackId="a"
                  fill={s.color}
                />
              ))}
            </BarChart>
          </ResponsiveContainer>
        </div>
        <div className="glass p-4">
          <div
            className="text-xs font-bold mb-3"
            style={{
              ...manrope,
              color: 'var(--text-secondary)',
            }}
          >
            Grounding pass rate by session (today)
          </div>
          <ResponsiveContainer width="100%" height={220}>
            <BarChart data={pr} barSize={36}>
              <CartesianGrid
                strokeDasharray="3 3"
                vertical={false}
                stroke="var(--border-subtle)"
              />
              <XAxis dataKey="l4" {...axis} />
              <YAxis
                domain={[80, 100]}
                allowDataOverflow={true}
                {...axis}
                unit="%"
              />
              <Tooltip
                {...tip}
                formatter={(v) => [`${v}%`, 'Grounding pass rate']}
              />
              <Bar
                dataKey="passRate"
                fill="var(--barcl-eagle)"
                radius={[4, 4, 0, 0]}
              />
            </BarChart>
          </ResponsiveContainer>
        </div>
      </div>
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
        <div className="glass p-4">
          <div
            className="text-xs font-bold mb-3"
            style={{
              ...manrope,
              color: 'var(--text-secondary)',
            }}
          >
            Adjustments drafted, auto vs. manual
          </div>
          <div className="flex items-center gap-4">
            <div
              className="shrink-0"
              style={{
                width: 140,
                height: 140,
              }}
            >
              <ResponsiveContainer width={140} height={140}>
                <PieChart>
                  <Pie
                    data={pie}
                    dataKey="value"
                    nameKey="name"
                    innerRadius={40}
                    outerRadius={62}
                    paddingAngle={2}
                  >
                    <Cell fill="var(--barcl-eagle)" />
                    <Cell fill="var(--bg-header)" />
                  </Pie>
                  <Tooltip {...tip} />
                </PieChart>
              </ResponsiveContainer>
            </div>
            <div
              className="hx-space-y-2 min-w-0 text-xs"
              style={{
                color: 'var(--text-secondary)',
              }}
            >
              <div className="flex items-center gap-2">
                <span
                  className="w-2.5 h-2.5 rounded-full"
                  style={{
                    background: 'var(--barcl-eagle)',
                  }}
                />
                {'Auto: '}
                {auto}
                {' ('}
                {adjs.length ? Math.round((auto / adjs.length) * 100) : 0}%)
              </div>
              <div className="flex items-center gap-2">
                <span
                  className="w-2.5 h-2.5 rounded-full"
                  style={{
                    background: 'var(--bg-header)',
                  }}
                />
                {'Manual: '}
                {manual}
                {' ('}
                {adjs.length ? Math.round((manual / adjs.length) * 100) : 0}%)
              </div>
              <div
                className="text-[10.5px] pt-1"
                style={{
                  color: 'var(--text-muted)',
                }}
              >
                Every adjustment, auto or manual, still needs a double-confirmed
                human sign-off before FAS posts to MOTIF.
              </div>
            </div>
          </div>
        </div>
        <div className="glass p-4 flex flex-col justify-center">
          <div
            className="text-xs font-bold mb-2"
            style={{
              ...manrope,
              color: 'var(--text-secondary)',
            }}
          >
            Reading these numbers
          </div>
          <ul
            className="text-xs hx-space-y-1.5 list-disc pl-4 leading-relaxed"
            style={{
              color: 'var(--text-muted)',
            }}
          >
            <li>
              Grounding pass rate comes from the numeric-grounding validator in
              each session, not model confidence.
            </li>
            <li>
              {'Decisions saved is the efficiency lever: '}
              {adjs.length}
              {' adjustments collapse into '}
              {patterns}
              {' patterns, so a controller makes '}
              {patterns}
              {' decisions rather than '}
              {adjs.length}.
            </li>
            <li>
              All figures on this page are for today's COB only. No historical
              approval rates are used.
            </li>
            <li>
              Breaks carried across sessions point at an upstream fix, not a
              daily adjustment.
            </li>
          </ul>
        </div>
      </div>
    </div>
  );
}
