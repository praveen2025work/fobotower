import { createLucideIcon } from 'lucide-react';

// The mock drew these five from its own path data. Newer lucide releases have
// redrawn some of them, so they are rebuilt here from the mock's exact paths.

export const Send = createLucideIcon('send', [
  [
    'path',
    {
      d: 'M14.536 21.686a.5.5 0 0 0 .937-.024l6.5-19a.496.496 0 0 0-.635-.635l-19 6.5a.5.5 0 0 0-.024.937l7.93 3.18a2 2 0 0 1 1.112 1.11z',
      key: 's1',
    },
  ],
  ['path', { d: 'm21.854 2.147-10.94 10.939', key: 's2' }],
]);

export const MessageSquare = createLucideIcon('message-square-text', [
  [
    'path',
    {
      d: 'M21 15a2 2 0 0 1-2 2H7l-4 4V5a2 2 0 0 1 2-2h14a2 2 0 0 1 2 2z',
      key: 'm1',
    },
  ],
  ['path', { d: 'M13 8H7', key: 'm2' }],
  ['path', { d: 'M17 12H7', key: 'm3' }],
]);

export const ShieldCheck = createLucideIcon('shield-check', [
  [
    'path',
    {
      d: 'M20 13c0 5-3.5 7.5-7.66 8.95a1 1 0 0 1-.67-.01C7.5 20.5 4 18 4 13V6a1 1 0 0 1 1-1c2 0 4.5-1.2 6.24-2.72a1.17 1.17 0 0 1 1.52 0C14.51 3.81 17 5 19 5a1 1 0 0 1 1 1z',
      key: 'c1',
    },
  ],
  ['path', { d: 'm9 12 2 2 4-4', key: 'c2' }],
]);

export const TableIcon = createLucideIcon('table', [
  ['rect', { x: '3', y: '3', width: '18', height: '18', rx: '2', key: 't1' }],
  ['path', { d: 'M3 9h18', key: 't2' }],
  ['path', { d: 'M3 15h18', key: 't3' }],
  ['path', { d: 'M9 3v18', key: 't4' }],
]);

export const FolderTree = createLucideIcon('folder', [
  [
    'path',
    {
      d: 'M20 20a2 2 0 0 0 2-2V8a2 2 0 0 0-2-2h-7.9a2 2 0 0 1-1.69-.9L9.6 3.9A2 2 0 0 0 7.93 3H4a2 2 0 0 0-2 2v13a2 2 0 0 0 2 2Z',
      key: 'f1',
    },
  ],
]);
