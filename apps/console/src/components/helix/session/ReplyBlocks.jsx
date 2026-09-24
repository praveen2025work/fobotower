import { TONES } from '../constants';
import { manrope, mono } from '../lib/format';
import { Callout, KvCards } from '../mcp/Blocks';

export function ReplyBlocks({ blocks }) {
  return (
    <div className="hx-space-y-2">
      {blocks.map((b, i) => {
        if (b.type === 'h')
          return (
            <div
              key={i}
              className="text-[12.5px] font-bold"
              style={{
                ...manrope,
                color: 'var(--text-primary)',
              }}
            >
              {b.text}
            </div>
          );
        if (b.type === 'p')
          return (
            <p
              key={i}
              className="text-[12.5px] leading-relaxed"
              style={{
                color: 'var(--text-secondary)',
              }}
            >
              {b.text}
            </p>
          );
        if (b.type === 'note')
          return (
            <p
              key={i}
              className="text-[11px] leading-relaxed"
              style={{
                color: 'var(--text-muted)',
              }}
            >
              {b.text}
            </p>
          );
        if (b.type === 'kv') return <KvCards key={i} items={b.items} />;
        if (b.type === 'ok' || b.type === 'warn' || b.type === 'risk')
          return <Callout key={i} tone={b.type} text={b.text} />;
        if (b.type === 'pre')
          return (
            <pre
              key={i}
              className="text-[11px] leading-relaxed rounded-lg px-3 py-2 whitespace-pre-wrap"
              style={{
                ...mono,
                background: 'var(--bg-muted)',
                color: 'var(--text-primary)',
                border: '1px solid var(--border-subtle)',
                margin: 0,
              }}
            >
              {b.text}
            </pre>
          );
        if (b.type === 'list')
          return (
            <div key={i}>
              {b.title && (
                <div
                  className="text-[10.5px] font-semibold mb-1"
                  style={{
                    color: b.tone ? TONES[b.tone].fg : 'var(--text-muted)',
                  }}
                >
                  {b.title}
                </div>
              )}
              <ul className="hx-space-y-1">
                {b.items.map((it, j) => (
                  <li
                    key={j}
                    className="flex items-start gap-1.5 text-[12px]"
                    style={{
                      color: 'var(--text-secondary)',
                    }}
                  >
                    <span
                      className="shrink-0 mt-1.5 w-1 h-1 rounded-full"
                      style={{
                        background: b.tone
                          ? TONES[b.tone].fg
                          : 'var(--text-muted)',
                      }}
                    />
                    {it}
                  </li>
                ))}
              </ul>
            </div>
          );
        return null;
      })}
    </div>
  );
}
