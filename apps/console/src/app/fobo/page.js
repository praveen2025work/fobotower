'use client';

import { useEffect, useState } from 'react';

import PatternGroupCard from '@/components/fobo/adjustments/PatternGroupCard';
import GroundingPanel from '@/components/fobo/grounding/GroundingPanel';
import PipelineRail from '@/components/fobo/pipeline/PipelineRail';
import RegionRail from '@/components/fobo/regions/RegionRail';
import RunScheduleCard from '@/components/fobo/schedule/RunScheduleCard';
import ConnectionError from '@/components/fobo/shell/ConnectionError';
import TopBar from '@/components/fobo/shell/TopBar';
import { useFoboRunStore } from '@/store/foboRunStore';
import { useFoboSessionStore } from '@/store/foboSessionStore';

const REGION_STYLE = {
  APAC: { background: 'var(--apac-bg)', color: 'var(--apac-text)' },
  EMEA: { background: 'var(--emea-bg)', color: 'var(--emea-text)' },
  AMER: { background: 'var(--amer-bg)', color: 'var(--amer-text)' },
};

export default function FoboControlTower() {
  const [tab, setTab] = useState('pipeline');
  const [openPattern, setOpenPattern] = useState(null);

  const regions = useFoboRunStore((s) => s.regions);
  const runWindows = useFoboRunStore((s) => s.runWindows);
  const stats = useFoboRunStore((s) => s.stats);
  const selectedRecId = useFoboRunStore((s) => s.selectedRecId);
  const selectRec = useFoboRunStore((s) => s.selectRec);
  const loadRuns = useFoboRunStore((s) => s.loadRuns);
  const runError = useFoboRunStore((s) => s.error);

  const sess = useFoboSessionStore();
  const { loadRec } = sess;

  useEffect(() => {
    loadRuns();
  }, [loadRuns]);

  // The rail chooses a rec; this loads it. Selecting a different rec in the
  // rail is the only navigation the screen has, so it has to actually work.
  useEffect(() => {
    if (selectedRecId) loadRec(selectedRecId);
  }, [selectedRecId, loadRec]);

  const error = runError ?? sess.error;
  if (error) {
    return (
      <ConnectionError
        message={error}
        onRetry={() => {
          loadRuns();
          if (selectedRecId) loadRec(selectedRecId);
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

  const header = sess.header;
  const awaiting = sess.patternGroups.reduce(
    (n, g) => n + g.break_ids.length,
    0,
  );
  const counts = {
    auto_posted: sess.patternGroups.filter((g) => g.mode === 'auto').length,
    awaiting_signoff: awaiting,
    not_open: header ? Math.max(0, (header.books_open ?? 0) - awaiting) : 0,
  };

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

          <section className="glass-card p-4 flex flex-col gap-4 min-h-[320px]">
            {sess.loading && (
              <p className="text-sm" style={{ color: 'var(--text-muted)' }}>
                Loading {selectedRecId}…
              </p>
            )}

            {!sess.loading && header && (
              <>
                <header className="flex flex-wrap items-center gap-2">
                  <h2
                    className="text-base font-bold"
                    style={{ fontFamily: 'var(--font-manrope), sans-serif' }}
                  >
                    {header.name}
                  </h2>
                  <span
                    className="pill font-semibold"
                    style={REGION_STYLE[header.region]}
                  >
                    {header.region}
                  </span>
                  <span
                    className="text-xs"
                    style={{ color: 'var(--text-muted)' }}
                  >
                    {header.rec_id} · {header.scheduled}
                    {header.completed ? ` · ${header.completed} IST` : ''} ·{' '}
                    {header.master_book} · COB {header.business_date}
                  </span>
                  <StatusPill state={sess.state} header={header} />
                </header>

                {sess.pipelineStages.length > 0 && (
                  <PipelineRail
                    stages={sess.pipelineStages}
                    currentStage={sess.pipelineStage}
                    counts={counts}
                  />
                )}

                {sess.state === 'clear' && (
                  <p className="text-sm" style={{ color: 'var(--text-muted)' }}>
                    Nothing to review on this rec. {header.books_open} of its
                    books are open and no breaks are outstanding.
                  </p>
                )}

                {sess.draft && (
                  <AnalysisPanel
                    draft={sess.draft}
                    modelSkipped={sess.modelSkipped}
                    evidenceGaps={sess.evidenceGaps}
                  />
                )}

                {sess.grounding.length > 0 && (
                  <GroundingPanel calls={sess.grounding} />
                )}

                {sess.patternGroups.length > 0 && (
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
                        {awaiting} adj · {sess.patternGroups.length} patterns ·
                        click a pattern for detail
                      </span>
                    </h3>

                    {sess.patternGroups.map((group) => (
                      <PatternGroupCard
                        key={group.group_id}
                        group={group}
                        deltas={sess.deltas}
                        breakBooks={sess.breakBooks}
                        reasons={sess.reasons}
                        meta={sess.groupMeta[group.group_id] ?? {}}
                        onOpenPattern={setOpenPattern}
                      />
                    ))}
                  </div>
                )}
              </>
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

      {openPattern && (
        <PatternDrawer
          group={openPattern}
          deltas={sess.deltas}
          breakBooks={sess.breakBooks}
          reasons={sess.reasons}
          onClose={() => setOpenPattern(null)}
        />
      )}
    </div>
  );
}

function StatusPill({ state, header }) {
  const label =
    state === 'clear'
      ? header.run_status === 'cleared'
        ? 'Cleared'
        : 'Not open yet'
      : header.status === 'awaiting_signoff'
        ? 'Awaiting Sign-off'
        : header.status;
  const tone =
    state === 'clear'
      ? { background: 'var(--clr-green-bg)', color: 'var(--clr-green)' }
      : { background: 'var(--clr-amber-bg)', color: 'var(--clr-amber)' };
  return (
    <span className="pill ml-auto font-medium" style={tone}>
      {label}
    </span>
  );
}

function AnalysisPanel({ draft, modelSkipped, evidenceGaps }) {
  return (
    <div className="flex flex-col gap-3">
      <div className="flex flex-wrap items-center gap-2">
        <h3
          className="text-sm font-bold"
          style={{ fontFamily: 'var(--font-manrope), sans-serif' }}
        >
          Agent Analysis
        </h3>
        <span
          className="pill"
          style={{ background: 'var(--clr-amber-bg)', color: 'var(--clr-amber)' }}
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
  );
}

function PatternDrawer({ group, deltas, breakBooks, reasons, onClose }) {
  const total = group.break_ids.reduce((sum, b) => sum + (deltas[b] ?? 0), 0);
  return (
    <div
      className="fixed inset-0 flex justify-end"
      style={{ background: 'rgba(0,30,69,0.32)', zIndex: 50 }}
      onClick={onClose}
    >
      <aside
        role="dialog"
        aria-label={`${group.label} detail`}
        className="h-full overflow-auto p-5 flex flex-col gap-4"
        style={{
          width: 420,
          background: 'var(--bg-card-solid)',
          borderLeft: '1px solid var(--border)',
        }}
        onClick={(e) => e.stopPropagation()}
      >
        <div className="flex items-start justify-between gap-3">
          <div>
            <h2
              className="text-lg font-bold"
              style={{ fontFamily: 'var(--font-manrope), sans-serif' }}
            >
              {group.label}
            </h2>
            <p className="text-xs" style={{ color: 'var(--text-muted)' }}>
              {group.pattern_code} · {group.break_ids.length} books today
              {group.historical_approval_rate != null &&
                ` · ${Math.round(group.historical_approval_rate * 100)}% historical approval`}
            </p>
          </div>
          <button
            type="button"
            onClick={onClose}
            aria-label="Close drawer"
            className="pill"
            style={{ background: 'var(--bg-hover)', color: 'var(--text-secondary)' }}
          >
            Close
          </button>
        </div>

        <div className="grid grid-cols-3 gap-2">
          <Tile label="Books today" value={group.break_ids.length} />
          <Tile
            label="Avg approval"
            value={
              group.historical_approval_rate != null
                ? `${Math.round(group.historical_approval_rate * 100)}%`
                : '—'
            }
          />
          <Tile
            label="Total"
            value={`$${Number(total).toLocaleString('en-US', { maximumFractionDigits: 0 })}`}
          />
        </div>

        <div>
          <div
            className="text-[11px] font-bold tracking-wide mb-1"
            style={{ color: 'var(--text-muted)' }}
          >
            BOOKS IN THIS PATTERN TODAY
          </div>
          <ul className="flex flex-col">
            {group.break_ids.map((b) => (
              <li
                key={b}
                className="py-1.5"
                style={{ borderTop: '1px solid var(--border-subtle)' }}
              >
                <div className="flex items-baseline justify-between gap-2">
                  <span
                    className="text-sm"
                    style={{ color: 'var(--text-primary)' }}
                  >
                    {breakBooks[b] ?? b}
                  </span>
                  <span
                    className="text-sm"
                    style={{
                      color: 'var(--text-primary)',
                      fontFamily: 'var(--font-mono), monospace',
                    }}
                  >
                    ${Number(deltas[b] ?? 0).toLocaleString('en-US', { minimumFractionDigits: 2 })}
                  </span>
                </div>
                <div className="text-xs" style={{ color: 'var(--text-muted)' }}>
                  {reasons[b] ?? ''}
                </div>
              </li>
            ))}
          </ul>
        </div>
      </aside>
    </div>
  );
}

function Tile({ label, value }) {
  return (
    <div
      className="rounded-lg p-2 text-center"
      style={{ background: 'var(--bg-muted)' }}
    >
      <div
        className="text-lg font-bold"
        style={{ color: 'var(--text-primary)' }}
      >
        {value}
      </div>
      <div className="text-[11px]" style={{ color: 'var(--text-muted)' }}>
        {label}
      </div>
    </div>
  );
}
