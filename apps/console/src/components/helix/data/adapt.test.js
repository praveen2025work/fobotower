import { describe, expect, it } from 'vitest';

import { adaptCall, adaptRec } from './adapt';

const call = (over = {}) => ({
  id: 'c1',
  server: 'mbrec',
  tool: 'get_break_legs',
  args: {},
  rows: [{ breakId: 'B-1', masterBook: 'PRIME-MB-01', leg: 'CATS', amount: 'USD 1.00' }],
  summary: '1 leg entries',
  ms: 12,
  status: 'ok',
  ...over,
});

describe('adaptCall', () => {
  it('shows only the columns the tool actually returned', () => {
    const keys = adaptCall(call()).columns.map((c) => c.key);
    expect(keys).toEqual(['breakId', 'masterBook', 'leg', 'amount']);
  });

  it('keeps a field that has no column spec rather than hiding it', () => {
    const c = adaptCall(call({ rows: [{ breakId: 'B-1', surprise: 'x' }] }));
    expect(c.columns.map((col) => col.key)).toEqual(['breakId', 'surprise']);
    expect(c.columns[1].label).toBe('Surprise');
  });

  it('derives every column for a tool it has never seen', () => {
    const c = adaptCall(call({ tool: 'new_tool', rows: [{ fooBar: 1 }] }));
    expect(c.columns).toEqual([{ key: 'fooBar', label: 'Foo Bar' }]);
  });

  it('prints a sub-millisecond call as "<1" instead of a bare 0', () => {
    expect(adaptCall(call({ ms: 0 })).ms).toBe('<1');
    expect(adaptCall(call({ ms: null })).ms).toBeNull();
  });

  it('treats missing rows as an empty table', () => {
    const c = adaptCall(call({ rows: undefined }));
    expect(c.rows).toEqual([]);
    expect(c.columns).toEqual([]);
  });
});

describe('adaptRec', () => {
  it('adapts the analysis calls and every message that carries calls', () => {
    const rec = adaptRec({
      id: 'R-1',
      calls: [call()],
      session: [
        { id: 'a0', role: 'agent', kind: 'analysis', calls: [call()] },
        { id: 'u1', role: 'user', text: 'hi' },
      ],
    });
    expect(rec.calls[0].columns).toHaveLength(4);
    expect(rec.session[0].calls[0].columns).toHaveLength(4);
    expect(rec.session[1]).toEqual({ id: 'u1', role: 'user', text: 'hi' });
  });

  it('tolerates a rec with no session yet', () => {
    expect(adaptRec({ id: 'R-2' })).toMatchObject({ calls: [], session: [] });
  });
});
