import { render, screen } from '@testing-library/react';
import { describe, expect, it } from 'vitest';
import { YamlDiff } from './YamlDiff';

const HEADER = [
  '# FOBO investigation workflow, version 3 (active)',
  '# Drafted by system; approved by system.',
  '# Note: n/a',
  '#',
  '# Upload this file in the Workflow tab to propose it as a draft; a second',
  '# Product Control user must approve it before new runs use it.',
].join('\n');

const before = `${HEADER}\nsettings:\n  gather:\n    priors_lookback_days: 180\n`;
const after = `${HEADER.replace('version 3', 'version 4')}\nsettings:\n  gather:\n    priors_lookback_days: 90\n`;

describe('YamlDiff', () => {
  it('shows one added and one removed line, plus the summary, for a changed lookback', () => {
    render(<YamlDiff before={before} after={after} />);
    expect(screen.getByText(/priors_lookback_days: 180/)).toBeInTheDocument();
    expect(screen.getByText(/priors_lookback_days: 90/)).toBeInTheDocument();
    expect(screen.getByText('1 lines added · 1 removed')).toBeInTheDocument();
  });

  it('says so when identical (ignoring the header)', () => {
    render(<YamlDiff before={before} after={before.replace('version 3', 'version 3 (still)')} />);
    expect(screen.getByText('Identical to the active version.')).toBeInTheDocument();
  });
});
