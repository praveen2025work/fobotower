import { render, screen, within } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { beforeEach, describe, expect, it, vi } from 'vitest';
import { YamlView } from './YamlView';

const TEXT = 'a: 1\nb: two\nc: 3';

beforeEach(() => {
  Object.defineProperty(navigator, 'clipboard', {
    value: { writeText: vi.fn() },
    writable: true,
    configurable: true,
  });
});

describe('YamlView', () => {
  it('renders every line with its line number', () => {
    render(<YamlView text={TEXT} />);
    expect(screen.getByTestId('yaml-line-number-1')).toHaveTextContent('1');
    expect(screen.getByTestId('yaml-line-number-2')).toHaveTextContent('2');
    expect(screen.getByTestId('yaml-line-number-3')).toHaveTextContent('3');
    expect(screen.getByTestId('yaml-line-2')).toHaveTextContent('b: two');
  });

  it('gives a key token the key styling hook', () => {
    render(<YamlView text={TEXT} />);
    const row = screen.getByTestId('yaml-line-1');
    const keyToken = row.querySelector('[data-kind="key"]');
    expect(keyToken).not.toBeNull();
    expect(keyToken).toHaveTextContent('a');
  });

  it('copies the full text and shows Copied', async () => {
    navigator.clipboard.writeText.mockResolvedValue();
    render(<YamlView text={TEXT} />);
    await userEvent.click(screen.getByRole('button', { name: 'Copy' }));
    expect(navigator.clipboard.writeText).toHaveBeenCalledWith(TEXT);
    expect(await screen.findByText('Copied')).toBeInTheDocument();
  });

  it('shows a fallback message when the clipboard rejects', async () => {
    navigator.clipboard.writeText.mockRejectedValue(new Error('denied'));
    render(<YamlView text={TEXT} />);
    await userEvent.click(screen.getByRole('button', { name: 'Copy' }));
    expect(await screen.findByText('Copy failed — select the text instead')).toBeInTheDocument();
  });
});
