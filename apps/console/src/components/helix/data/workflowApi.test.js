import { beforeEach, expect, it, vi } from 'vitest';
import * as client from '@/lib/apiClient';
import { approveVersion, fetchGraph, fetchVersionYaml, saveDraft, uploadYaml } from './workflowApi';

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

it('fetches the graph for a version', async () => {
  await fetchGraph(3);
  expect(client.get).toHaveBeenCalledWith('/api/workflow/graph?version=3');
});

it('fetches the active graph when no version is given', async () => {
  await fetchGraph();
  expect(client.get).toHaveBeenCalledWith('/api/workflow/graph');
});

it('fetches a version’s YAML as text', async () => {
  client.getText.mockResolvedValue('version: 4\n');
  await expect(fetchVersionYaml(4)).resolves.toBe('version: 4\n');
  expect(client.getText).toHaveBeenCalledWith('/api/workflow/versions/4/yaml');
});
