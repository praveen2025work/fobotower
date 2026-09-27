import { get, getText, post } from '@/lib/apiClient';

/** Every call the Workflow tab makes to the orchestrator. */

export const fetchWorkflow = () => get('/api/workflow');

export const fetchVersions = () => get('/api/workflow/versions');

export const fetchVersion = (n) => get(`/api/workflow/versions/${n}`);

export const fetchRebased = (n) => get(`/api/workflow/versions/${n}/rebased`);

/** A version's YAML as plain text, for the readable YAML tab. */
export const fetchVersionYaml = (n) => getText(`/api/workflow/versions/${n}/yaml`);

/** The compiled graph and why it routes the way it does, for a version
 * (default: active). */
export const fetchGraph = (version) =>
  get('/api/workflow/graph' + (version ? `?version=${version}` : ''));

export const validateWorkflow = (config) => post('/api/workflow/validate', { config });

export const saveDraft = ({ config, note, basedOn }) =>
  post('/api/workflow/drafts', { config, note, based_on: basedOn });

export const uploadYaml = ({ yaml, note }) => post('/api/workflow/drafts/yaml', { yaml, note });

/** The key is chosen once per confirmation, so a retry of the same click can
 * never approve twice; the API refuses a repeated key. */
export const approveVersion = (n, key) =>
  post(`/api/workflow/versions/${n}/approve`, null, { 'Idempotency-Key': key });

export const rejectVersion = (n, reason) => post(`/api/workflow/versions/${n}/reject`, { reason });

export async function downloadYaml(n) {
  const text = await getText(`/api/workflow/versions/${n}/yaml`);
  const url = URL.createObjectURL(new Blob([text], { type: 'text/yaml' }));
  const a = document.createElement('a');
  a.href = url;
  a.download = `fobo-investigation-v${n}.yaml`;
  a.click();
  URL.revokeObjectURL(url);
}
