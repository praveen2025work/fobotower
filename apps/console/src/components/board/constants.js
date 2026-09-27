import {
  TriangleAlert as Alert,
  BellRing as Bell,
  CircleCheck,
  Database,
  ShieldCheck,
  Sparkles,
  CloudUpload as Upload,
  UserCheck,
  X as XIcon,
  Zap,
} from 'lucide-react';

export const PIPELINE = [
  {
    key: 'ingest',
    label: 'MB Rec readiness',
    sub: 'One Fin UX events',
    icon: Database,
  },
  {
    key: 'ready',
    label: 'Ready event',
    sub: 'One Fin UX → Helix',
    icon: Zap,
  },
  {
    key: 'analysis',
    label: 'Helix Session Analysis',
    sub: 'Agent One',
    icon: Sparkles,
  },
  {
    key: 'signoff',
    label: 'Human Sign-off',
    sub: 'Double confirmed',
    icon: UserCheck,
  },
  {
    key: 'posting',
    label: 'Post to MOTIF',
    sub: 'via FAS (MCP)',
    icon: Upload,
  },
];

export const STEP_SECTION = {
  ingest: 'session',
  ready: 'session',
  analysis: 'session',
  signoff: 'adjustments',
  posting: 'adjustments',
};

export const SECTION_LABEL = {
  session: 'Helix session',
  adjustments: 'Drafted adjustments',
};

export const currentStepIndex = (rec) => {
  const i = rec.steps.findIndex((s) => s === 'active' || s === 'blocked');
  return i >= 0 ? i : rec.steps.lastIndexOf('done');
};

export const GROUPS = [
  {
    key: 'CATS-MOTIF',
    label: 'CATS vs MOTIF',
    short: 'CATS v MOTIF',
    bg: 'var(--clr-blue-bg)',
    text: 'var(--clr-blue)',
  },
  {
    key: 'RF-CASHCOLL',
    label: 'Rec Factory — Cash & Collateral',
    short: 'Rec Factory',
    bg: 'var(--clr-purple-bg)',
    text: 'var(--clr-purple)',
  },
];

export const groupOf = (key) =>
  GROUPS.find((g2) => g2.key === key) || GROUPS[0];

export const STATUS = {
  Cleared: {
    bg: 'var(--clr-green-bg)',
    text: 'var(--clr-green)',
    dot: 'var(--clr-green)',
  },
  'In Progress': {
    bg: 'var(--clr-blue-bg)',
    text: 'var(--clr-blue)',
    dot: 'var(--barcl-eagle)',
  },
  'Awaiting Sign-off': {
    bg: 'var(--clr-amber-bg)',
    text: 'var(--clr-amber)',
    dot: 'var(--clr-amber-dot)',
  },
  Blocked: {
    bg: 'var(--clr-red-bg)',
    text: 'var(--clr-red)',
    dot: 'var(--clr-red)',
  },
  'Awaiting Ready': {
    bg: 'var(--clr-grey-bg)',
    text: 'var(--clr-grey)',
    dot: 'var(--clr-grey)',
  },
};

export const STATUS_ORDER = [
  'Cleared',
  'In Progress',
  'Awaiting Sign-off',
  'Blocked',
  'Awaiting Ready',
];

export const ACTIVITY_STYLE = {
  cleared: {
    icon: CircleCheck,
    cssVar: '--clr-green',
  },
  unlocked: {
    icon: Upload,
    cssVar: '--clr-blue',
  },
  notify: {
    icon: Bell,
    cssVar: '--bg-header',
  },
  awaiting: {
    icon: UserCheck,
    cssVar: '--clr-amber',
  },
  blocked: {
    icon: Alert,
    cssVar: '--clr-red',
  },
  progress: {
    icon: Sparkles,
    cssVar: '--barcl-eagle',
  },
  approved: {
    icon: ShieldCheck,
    cssVar: '--clr-green',
  },
  event: {
    icon: Zap,
    cssVar: '--barcl-eagle',
  },
  rejected: {
    icon: XIcon,
    cssVar: '--clr-red',
  },
};

export const BAR_SEGMENTS = [
  {
    key: 'autoPost',
    label: 'Auto-posted',
    color: 'var(--bar-auto)',
  },
  {
    key: 'cleared',
    label: 'Cleared',
    color: 'var(--bar-cleared)',
  },
  {
    key: 'awaiting',
    label: 'Awaiting sign-off',
    color: 'var(--bar-awaiting)',
  },
  {
    key: 'analysing',
    label: 'In analysis',
    color: 'var(--bar-analysing)',
  },
  {
    key: 'blocked',
    label: 'Blocked',
    color: 'var(--bar-blocked)',
  },
  {
    key: 'notOpen',
    label: 'Not open yet',
    color: 'var(--bar-notopen)',
  },
];

export const SUGGESTIONS = {
  'Awaiting Sign-off': [
    'What is safe to approve?',
    "Summarise what's pending",
    'Explain B-12',
    'Draft a chase note for the desk',
    'Show the MCP data',
  ],
  Cleared: [
    "Summarise what's pending",
    'Explain the manual adjustment',
    'Show the MCP data',
    'Were all figures grounded?',
  ],
  Blocked: ['What should I do next?', 'Show the MCP data'],
};

export const TONES = {
  ok: {
    bg: 'var(--clr-green-bg)',
    fg: 'var(--clr-green)',
    icon: CircleCheck,
  },
  warn: {
    bg: 'var(--clr-amber-bg)',
    fg: 'var(--clr-amber)',
    icon: Alert,
  },
  risk: {
    bg: 'var(--clr-red-bg)',
    fg: 'var(--clr-red)',
    icon: Alert,
  },
  info: {
    bg: 'var(--clr-blue-bg)',
    fg: 'var(--clr-blue)',
    icon: Sparkles,
  },
};

export const eventLabel = (r) =>
  r.readyAt ? `Ready ${r.readyAt}` : `MB Rec ${r.mb.available}/${r.mb.total}`;

export const CONFIDENCE = {
  HIGH: {
    bg: 'var(--clr-green-bg)',
    text: 'var(--clr-green)',
    dot: 'var(--clr-green)',
    label: 'High confidence',
  },
  MEDIUM: {
    bg: 'var(--clr-amber-bg)',
    text: 'var(--clr-amber)',
    dot: 'var(--clr-amber-dot)',
    label: 'Needs your review',
  },
  BLOCKED: {
    bg: 'var(--clr-red-bg)',
    text: 'var(--clr-red)',
    dot: 'var(--clr-red)',
    label: 'Blocked',
  },
  RUNNING: {
    bg: 'var(--clr-blue-bg)',
    text: 'var(--clr-blue)',
    dot: 'var(--barcl-eagle)',
    label: 'Running…',
  },
};
