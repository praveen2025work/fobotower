import { get, post } from '@/lib/apiClient';

/** Every call the Helix console makes to the orchestrator. */

export const fetchBoard = () => get('/api/helix/board');

export const fetchRec = (recId) => get(`/api/helix/recs/${recId}`);

export const fetchTrace = (recId) => get(`/api/recs/${recId}/trace`);

export const askSession = (recId, message) =>
  post(`/api/helix/recs/${recId}/messages`, { message });

/**
 * One key per confirmed decision. The API refuses a repeated key, so a retry
 * of the same request can never post the same adjustments twice.
 */
export const decide = (recId, { ids, decision, reason }) =>
  post(
    `/api/helix/recs/${recId}/decisions`,
    { ids, decision, reason: reason || null },
    { 'Idempotency-Key': crypto.randomUUID() },
  );
