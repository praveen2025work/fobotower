import { render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { beforeEach, expect, it, vi } from 'vitest';
import { ApiError } from '@/lib/apiClient';
import * as api from '../data/workflowApi';
import { YamlUpload } from './YamlUpload';

vi.mock('../data/workflowApi', () => ({ uploadYaml: vi.fn() }));

beforeEach(() => vi.clearAllMocks());

const fill = async () => {
  // user-event v14 treats '[' as the start of a special key descriptor, so a
  // literal '[' must be escaped as '[[' — this still types 'steps: []'.
  await userEvent.type(screen.getByLabelText('YAML text'), 'steps: [[]');
  await userEvent.type(screen.getByLabelText('Change note'), 'from the repo');
};

it('turns pasted YAML into a draft', async () => {
  api.uploadYaml.mockResolvedValue({ number: 5, status: 'draft' });
  const onUploaded = vi.fn();
  render(<YamlUpload onUploaded={onUploaded} onClose={vi.fn()} />);
  await fill();
  await userEvent.click(screen.getByRole('button', { name: 'Create draft' }));
  expect(api.uploadYaml).toHaveBeenCalledWith({ yaml: 'steps: []', note: 'from the repo' });
  expect(onUploaded).toHaveBeenCalledWith({ number: 5, status: 'draft' });
});

it('shows the server’s line-numbered problems', async () => {
  api.uploadYaml.mockRejectedValue(
    new ApiError('the YAML could not be read', {
      status: 422,
      errors: ["line 3, column 7: expected ',' or ']'"],
    }),
  );
  render(<YamlUpload onUploaded={vi.fn()} onClose={vi.fn()} />);
  await fill();
  await userEvent.click(screen.getByRole('button', { name: 'Create draft' }));
  expect(await screen.findByText(/line 3, column 7/)).toBeInTheDocument();
});
