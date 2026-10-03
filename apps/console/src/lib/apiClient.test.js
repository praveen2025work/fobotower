import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { ApiError, DEV_CALLER_KEY, devCaller, get, post, setDevCaller } from './apiClient';

const reply = (status, body) => ({
  ok: status < 400,
  status,
  json: async () => {
    if (body === undefined) throw new Error('no body');
    return body;
  },
  text: async () => JSON.stringify(body),
});

beforeEach(() => {
  global.fetch = vi.fn();
  setDevCaller(null);
});

afterEach(() => vi.restoreAllMocks());

describe('apiClient', () => {
  it('sends no identity header by default', async () => {
    fetch.mockResolvedValue(reply(200, {}));
    await get('/x');
    expect(fetch.mock.calls[0][1].headers).toEqual({});
  });

  it('sends X-Dev-Caller once a dev caller is chosen', async () => {
    setDevCaller('asha');
    fetch.mockResolvedValue(reply(200, {}));
    await post('/x', { a: 1 });
    expect(fetch.mock.calls[0][1].headers['X-Dev-Caller']).toBe('asha');
  });

  it('remembers the choice across reloads', () => {
    setDevCaller('asha');
    expect(window.localStorage.getItem(DEV_CALLER_KEY)).toBe('asha');
  });

  it('still switches when browser storage is blocked', async () => {
    vi.spyOn(Storage.prototype, 'setItem').mockImplementation(() => {
      throw new Error('blocked');
    });
    vi.spyOn(Storage.prototype, 'getItem').mockImplementation(() => {
      throw new Error('blocked');
    });
    setDevCaller('asha');
    fetch.mockResolvedValue(reply(200, {}));
    await get('/x');
    expect(fetch.mock.calls[0][1].headers['X-Dev-Caller']).toBe('asha');
  });

  it('surfaces every problem the server listed', async () => {
    fetch.mockResolvedValue(
      reply(422, { detail: { message: 'workflow is invalid', errors: ['a', 'b'] } }),
    );
    const err = await post('/x', {}).catch((e) => e);
    expect(err).toBeInstanceOf(ApiError);
    expect([err.message, err.status, err.errors]).toEqual(['workflow is invalid', 422, ['a', 'b']]);
  });

  it('keeps a plain detail as the message', async () => {
    fetch.mockResolvedValue(reply(403, { detail: 'a second Product Control user must approve' }));
    const err = await post('/x', {}).catch((e) => e);
    expect(err.message).toBe('a second Product Control user must approve');
    expect(err.errors).toEqual([]);
  });

  it('turns request validation errors into readable lines', async () => {
    fetch.mockResolvedValue(reply(422, { detail: [{ loc: ['body', 'note'], msg: 'Field required' }] }));
    const err = await post('/x', {}).catch((e) => e);
    expect(err.message).toBe('note: Field required');
  });

  it('falls back to the method, path and status', async () => {
    fetch.mockResolvedValue(reply(500));
    const err = await get('/x').catch((e) => e);
    expect(err.message).toBe('GET /x failed: 500');
  });

  it('clears a dev caller the server no longer recognises, so the switch reappears', async () => {
    setDevCaller('ghost');
    fetch.mockResolvedValue(reply(400, { detail: 'unknown dev caller: ghost' }));
    const err = await get('/x').catch((e) => e);
    expect(err).toBeInstanceOf(ApiError);
    expect(devCaller()).toBeNull();
    expect(window.localStorage.getItem(DEV_CALLER_KEY)).toBeNull();
  });

  it('leaves a recognised dev caller alone on an unrelated 400', async () => {
    setDevCaller('asha');
    fetch.mockResolvedValue(reply(400, { detail: 'a rejection requires a reason' }));
    await post('/x', {}).catch(() => {});
    expect(devCaller()).toBe('asha');
  });
});
