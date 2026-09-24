import { beforeEach, expect, it, vi } from 'vitest';
import * as client from '@/lib/apiClient';
import { approveVersion, saveDraft, uploadYaml } from './workflowApi';

vi.mock('@/lib/apiClient', () => ({
  API_BASE: 'http://api',
  get: vi.fn(),
  getText: vi.fn(),
  post: vi.fn(),
}));

beforeEach(() => vi.clearAllMocks());

it('saves a draft with the API field names', async () => {
  await saveDraft({ config: { steps: [] }, note: 'why', basedOn: 3 });
  expect(client.post).toHaveBeenCalledWith('/api/workflow/drafts', {
    config: { steps: [] },
    note: 'why',
    based_on: 3,
  });
});

it('approves with the idempotency key the dialog chose', async () => {
  await approveVersion(5, 'key-1');
  expect(client.post).toHaveBeenCalledWith('/api/workflow/versions/5/approve', null, {
    'Idempotency-Key': 'key-1',
  });
});

it('uploads YAML text with its note', async () => {
  await uploadYaml({ yaml: 'steps: []', note: 'n' });
  expect(client.post).toHaveBeenCalledWith('/api/workflow/drafts/yaml', { yaml: 'steps: []', note: 'n' });
});
