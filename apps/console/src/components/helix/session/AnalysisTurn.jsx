import { CONFIDENCE } from '../constants';
import { Callout } from '../mcp/Blocks';
import { CallList } from '../mcp/ToolCall';
import { Label } from '../ui/Kpi';

export function AnalysisTurn({ rec, calls, onInspect }) {
  const a = rec.analysis,
    conf = CONFIDENCE[a.confidence] || CONFIDENCE.MEDIUM,
    blocked = a.confidence === 'BLOCKED';
  return (
    <div className="hx-space-y-2.5">
      <div className="flex items-center gap-2 flex-wrap">
        <span
          className="text-[12px] font-semibold px-2.5 py-0.5 rounded-full flex items-center gap-1.5"
          style={{
            backgroundColor: conf.bg,
            color: conf.text,
          }}
        >
          <span
            className="w-2 h-2 rounded-full"
            style={{
              backgroundColor: conf.dot,
            }}
          />
          {conf.label}
        </span>
        <span
          className="text-[10.5px]"
          style={{
            color: 'var(--text-muted)',
          }}
        >
          Automated session analysis
        </span>
      </div>
      <div>
        <Label>What happened</Label>
        <p
          className="text-[13px] leading-relaxed"
          style={{
            color: 'var(--text-primary)',
          }}
        >
          {a.what}
        </p>
      </div>
      {a.why && (
        <div>
          <Label>Why</Label>
          <p
            className="text-[13px] leading-relaxed"
            style={{
              color: 'var(--text-secondary)',
            }}
          >
            {a.why}
          </p>
        </div>
      )}
      {a.action && (
        <Callout
          tone={blocked ? 'risk' : a.confidence === 'RUNNING' ? 'info' : 'ok'}
          title="What to do"
          text={a.action}
        />
      )}
      {a.risk && (
        <Callout tone="warn" title="Risk / watch point" text={a.risk} />
      )}
      {a.confidenceNote && (
        <div
          className="text-[11px] leading-relaxed"
          style={{
            color: 'var(--text-muted)',
          }}
        >
          <span
            className="font-semibold"
            style={{
              color: 'var(--text-secondary)',
            }}
          >
            {'Confidence basis: '}
          </span>
          {a.confidenceNote}
        </div>
      )}
      <CallList
        calls={calls}
        onInspect={onInspect}
        title="Grounding, MCP calls"
      />
    </div>
  );
}
