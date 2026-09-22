'use client';

import { useEffect, useState } from 'react';

import PipelineRail from '@/components/fobo/pipeline/PipelineRail';
import RegionRail from '@/components/fobo/regions/RegionRail';
import RunScheduleCard from '@/components/fobo/schedule/RunScheduleCard';
import ConnectionError from '@/components/fobo/shell/ConnectionError';
import TopBar from '@/components/fobo/shell/TopBar';
import { useRunStream } from '@/hooks/useRunStream';
import { useFoboRunStore } from '@/store/foboRunStore';
import { useFoboSessionStore } from '@/store/foboSessionStore';

const SESSION_ID = 'sess-r1055';

const REGION_STYLE = {
  APAC: { background: 'var(--apac-bg)', color: 'var(--apac-text)' },
  EMEA: { background: 'var(--emea-bg)', color: 'var(--emea-text)' },
  AMER: { background: 'var(--amer-bg)', color: 'var(--amer-text)' },
};

export default function FoboControlTower() {
  const [tab, setTab] = useState('pipeline');

  const regions = useFoboRunStore((s) => s.regions);
  const runWindows = useFoboRunStore((s) => s.runWindows);
  const stats = useFoboRunStore((s) => s.stats);
  const selectedRecId = useFoboRunStore((s) => s.selectedRecId);
  const selectRec = useFoboRunStore((s) => s.selectRec);
  const loadRuns = useFoboRunStore((s) => s.loadRuns);
  const runError = useFoboRunStore((s) => s.error);

  const session = useFoboSessionStore((s) => s.session);
  const draft = useFoboSessionStore((s) => s.draft);
  const patternGroups = useFoboSessionStore((s) => s.patternGroups);
  const deltas = useFoboSessionStore((s) => s.deltas);
  const breakBooks = useFoboSessionStore((s) => s.breakBooks);
  const pipelineStages = useFoboSessionStore((s) => s.pipelineStages);
  const pipelineStage = useFoboSessionStore((s) => s.pipelineStage);
  const evidenceGaps = useFoboSessionStore((s) => s.evidenceGaps);
  const modelSkipped = useFoboSessionStore((s) => s.modelSkipped);
  const progress = useFoboSessionStore((s) => s.progress);
  const investigate = useFoboSessionStore((s) => s.investigate);
  const sessionError = useFoboSessionStore((s) => s.error);

  useEffect(() => {
    loadRuns();
  }, [loadRuns]);

  useEffect(() => {
    investigate(SESSION_ID);
  }, [investigate]);

  useRunStream(SESSION_ID);

  const error = runError ?? sessionError;
  if (error) {
    return (
      <ConnectionError
        message={error}
        onRetry={() => {
          loadRuns();
          investigate(SESSION_ID);
        }}
      />
    );
  }

  if (!stats) {
    return (
      <p className="p-6 text-sm" style={{ color: 'var(--text-muted)' }}>
        Loading…
      </p>
    );
  }

  const awaiting = patternGroups.reduce((n, g) => n + g.break_ids.length, 0);
  const counts = { auto_posted: 3, awaiting_signoff: awaiting, not_open: 2 };

  return (
    <div className="min-h-screen flex flex-col">
      <TopBar stats={stats} activeTab={tab} onTabChange={setTab} />

      <main className="flex-1 p-4 flex flex-col gap-4">
        <RunScheduleCard
          stats={stats}
          regions={regions}
          runWindows={runWindows}
        />

        <div
          className="grid gap-4 items-start"
          style={{ gridTemplateColumns: '260px minmax(0, 1fr)' }}
        >
          <RegionRail
            regions={regions}
            selectedRecId={selectedRecId}
            onSelectRec={selectRec}
          />

          <section className="glass-card p-4 flex flex-col gap-4">
            {session && (
              <header className="flex flex-wrap items-center gap-2">
                <h2
                  className="text-base font-bold"
                  style={{ fontFamily: 'var(--font-manrope), sans-serif' }}
                >
                  Rec Factory — Cash Recon
                </h2>
                <span
                  className="pill font-semibold"
                  style={REGION_STYLE[session.region]}
                >
                  {session.region}
                </span>
                <span className="text-xs" style={{ color: 'var(--text-muted)' }}>
                  {session.reconciliation_id} · {session.master_book} · COB{' '}
                  {session.business_date}
                </span>
                <span
                  className="pill ml-auto font-medium"
                  style={{
                    background: 'var(--clr-amber-bg)',
                    color: 'var(--clr-amber)',
                  }}
                >
                  {session.status === 'awaiting_signoff'
                    ? 'Awaiting Sign-off'
                    : session.status}
                </span>
              </header>
            )}

            {pipelineStages.length > 0 && (
              <PipelineRail
                stages={pipelineStages}
                currentStage={pipelineStage}
                counts={counts}
              />
            )}

            {progress && (
              <p className="text-xs" style={{ color: 'var(--text-muted)' }}>
                {progress.node} · {progress.breaks_processed}/
                {progress.breaks_total} breaks
              </p>
            )}

            {draft && (
              <div className="flex flex-col gap-3">
                <div className="flex items-center gap-2">
                  <h3
                    className="text-sm font-bold"
                    style={{ fontFamily: 'var(--font-manrope), sans-serif' }}
                  >
                    Agent Analysis
                  </h3>
                  <span
                    className="pill"
                    style={{
                      background: 'var(--clr-amber-bg)',
                      color: 'var(--clr-amber)',
                    }}
                  >
                    Needs your review
                  </span>
                  {modelSkipped && (
                    <span
                      className="pill"
                      style={{
                        background: 'var(--clr-green-bg)',
                        color: 'var(--clr-green)',
                      }}
                    >
                      Deterministic · no model call
                    </span>
                  )}
                </div>

                {[
                  ['WHAT HAPPENED', draft.what_happened],
                  ['WHY', draft.why],
                  ['WHAT TO DO', draft.what_to_do],
                  ['RISK / WATCH POINT', draft.risk],
                ].map(([heading, body]) => (
                  <div key={heading}>
                    <div
                      className="text-[11px] font-bold tracking-wide mb-0.5"
                      style={{ color: 'var(--text-muted)' }}
                    >
                      {heading}
                    </div>
                    <p
                      className="text-sm leading-relaxed"
                      style={{ color: 'var(--text-secondary)' }}
                    >
                      {body}
                    </p>
                  </div>
                ))}

                <p className="text-xs" style={{ color: 'var(--text-muted)' }}>
                  Confidence basis: {draft.confidence_basis}
                  {evidenceGaps.length === 0 &&
                    ' Validation passed: every figure traces to a computed delta.'}
                </p>
              </div>
            )}

            {patternGroups.length > 0 && (
              <div className="flex flex-col gap-3">
                <h3
                  className="text-sm font-bold"
                  style={{ fontFamily: 'var(--font-manrope), sans-serif' }}
                >
                  Drafted Adjustments
                  <span
                    className="ml-2 text-xs font-normal"
                    style={{ color: 'var(--text-muted)' }}
                  >
                    {awaiting} adj · {patternGroups.length} patterns
                  </span>
                </h3>

                {patternGroups.map((group) => (
                  <PatternGroupCard
                    key={group.group_id}
                    group={group}
                    deltas={deltas}
                    breakBooks={breakBooks}
                  />
                ))}
              </div>
            )}
          </section>
        </div>
      </main>

      <footer
        className="px-6 py-3 text-center text-xs"
        style={{ color: 'var(--text-muted)' }}
      >
        Draft UI — illustrative data. Every posting step still requires human
        sign-off before MOTIF posting.
      </footer>
    </div>
  );
}

function PatternGroupCard({ group, deltas = {}, breakBooks = {} }) {
  const total = group.break_ids.reduce((sum, b) => sum + (deltas[b] ?? 0), 0);
  const auto = group.mode === 'auto';

  return (
    <div
      className="rounded-xl p-3"
      style={{
        background: 'var(--bg-muted)',
        border: '1px solid var(--border-subtle)',
      }}
    >
      <div className="flex flex-wrap items-center gap-2">
        <span
          className="pill font-semibold"
          style={{
            background: auto ? 'var(--clr-purple-bg)' : 'var(--bg-hover)',
            color: auto ? 'var(--clr-purple)' : 'var(--text-secondary)',
          }}
        >
          {auto ? 'Auto' : 'Manual'}
        </span>
        <span
          className="text-sm font-semibold"
          style={{ color: 'var(--text-primary)' }}
        >
          {group.label}
        </span>
        <span
          className="pill"
          style={{ background: 'var(--bg-hover)', color: 'var(--text-muted)' }}
        >
          {group.pattern_code}
        </span>
        <span className="text-xs" style={{ color: 'var(--text-muted)' }}>
          {group.break_ids.length} books
        </span>
        {group.historical_approval_rate !== null && (
          <span
            className="pill"
            style={{
              background: 'var(--clr-green-bg)',
              color: 'var(--clr-green)',
            }}
          >
            {Math.round(group.historical_approval_rate * 100)}% prior approval
          </span>
        )}
        <span
          className="ml-auto text-sm font-semibold"
          style={{ color: 'var(--text-primary)', fontFamily: 'var(--font-mono), monospace' }}
        >
          ${total.toLocaleString('en-US', { minimumFractionDigits: 2 })}
        </span>
      </div>

      <ul className="mt-2 flex flex-col gap-0.5">
        {group.break_ids.map((breakId) => (
          <li
            key={breakId}
            className="flex items-baseline justify-between text-xs"
            style={{ color: 'var(--text-secondary)' }}
          >
            <span>{breakBooks[breakId] ?? breakId}</span>
            <span style={{ fontFamily: 'var(--font-mono), monospace' }}>
              ${(deltas[breakId] ?? 0).toLocaleString('en-US', {
                minimumFractionDigits: 2,
              })}
            </span>
          </li>
        ))}
      </ul>
    </div>
  );
}
