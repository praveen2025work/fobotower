import { mono } from '../lib/format';
import { diffLines, stripHeader } from './yamlText';

const ROW_STYLE = {
  add: { background: 'var(--clr-green-bg)', color: 'var(--clr-green)' },
  del: { background: 'var(--clr-red-bg)', color: 'var(--clr-red)' },
  same: { color: 'var(--text-primary)' },
};

const MARKER = { add: '+', del: '−', same: ' ' };

/** A unified diff of two YAML texts, ignoring the header (it names the
 *  version and would be noise here — the same reason `Changes` shows a
 *  readable list instead of a raw diff). */
export function YamlDiff({ before, after }) {
  const rows = diffLines(stripHeader(before), stripHeader(after));
  const added = rows.filter((r) => r.kind === 'add').length;
  const removed = rows.filter((r) => r.kind === 'del').length;
  const changed = added > 0 || removed > 0;
  return (
    <div className="flex flex-col gap-1.5 min-w-0">
      <p className="text-[11.5px]" style={{ color: 'var(--text-secondary)' }}>
        {changed ? `${added} lines added · ${removed} removed` : 'Identical to the active version.'}
      </p>
      {changed && (
        <div
          className="rounded-lg overflow-auto"
          style={{ background: 'var(--bg-muted)', border: '1px solid var(--border)', maxHeight: 360 }}
        >
          <pre className="text-[11.5px] leading-[1.5] py-2" style={mono}>
            {rows.map((row, i) => (
              <div
                key={i}
                className="flex px-2 whitespace-pre"
                style={ROW_STYLE[row.kind]}
              >
                <span aria-hidden="true" className="select-none shrink-0 mr-2 w-3">
                  {MARKER[row.kind]}
                </span>
                <code>{row.line === '' ? ' ' : row.line}</code>
              </div>
            ))}
          </pre>
        </div>
      )}
    </div>
  );
}
