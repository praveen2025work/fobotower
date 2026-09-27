import { useEffect, useState } from 'react';
import { mono } from '../lib/format';
import { tokenizeYamlLine } from './yamlText';

const TOKEN_STYLE = {
  comment: { color: 'var(--text-muted)', fontStyle: 'italic' },
  key: { color: 'var(--clr-blue)' },
  string: { color: 'var(--clr-green)' },
  number: { color: 'var(--clr-purple)' },
  bool: { color: 'var(--clr-purple)' },
  punct: { color: 'var(--text-muted)' },
  text: { color: 'var(--text-primary)' },
};

const COPY_LABEL = {
  idle: 'Copy',
  copied: 'Copied',
  error: 'Copy failed — select the text instead',
};

/** A readable rendering of one YAML text: a line-number gutter, coloured
 *  tokens and a Copy button. Horizontal scroll stays inside the block; the
 *  page itself never scrolls sideways because of it. */
export function YamlView({ text }) {
  const [copyState, setCopyState] = useState('idle');
  useEffect(() => {
    if (copyState === 'idle') return undefined;
    const t = setTimeout(() => setCopyState('idle'), 2000);
    return () => clearTimeout(t);
  }, [copyState]);

  const copy = async () => {
    try {
      await navigator.clipboard.writeText(text);
      setCopyState('copied');
    } catch {
      setCopyState('error');
    }
  };

  const lines = text.split('\n');
  return (
    <div className="flex flex-col gap-1.5 min-w-0">
      <div className="flex items-center justify-end">
        <button
          type="button"
          onClick={copy}
          className="text-[11px] font-semibold px-2.5 py-1 rounded-full"
          style={{ border: '1px solid var(--border)', color: 'var(--text-secondary)' }}
        >
          {COPY_LABEL[copyState]}
        </button>
      </div>
      <div
        className="rounded-lg overflow-auto"
        style={{ background: 'var(--bg-muted)', border: '1px solid var(--border)', maxHeight: 360 }}
      >
        <pre className="text-[11.5px] leading-[1.5] py-2" style={mono}>
          {lines.map((line, i) => (
            <div key={i} data-testid={`yaml-line-${i + 1}`} className="flex px-2 whitespace-pre">
              <span
                aria-hidden="true"
                data-testid={`yaml-line-number-${i + 1}`}
                className="select-none text-right shrink-0 mr-3"
                style={{ color: 'var(--text-muted)', minWidth: 28 }}
              >
                {i + 1}
              </span>
              <code>
                {tokenizeYamlLine(line).map((token, j) => (
                  <span key={j} data-kind={token.kind} style={TOKEN_STYLE[token.kind]}>
                    {token.text}
                  </span>
                ))}
                {line === '' && ' '}
              </code>
            </div>
          ))}
        </pre>
      </div>
    </div>
  );
}
