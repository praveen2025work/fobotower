/**
 * Inline stroke icons, sized to the surrounding text.
 *
 * Emoji were standing in for these: they render differently on every
 * platform, ignore currentColor, and sit off the text baseline.
 */
const base = {
  viewBox: '0 0 24 24',
  fill: 'none',
  stroke: 'currentColor',
  strokeWidth: 2,
  strokeLinecap: 'round',
  strokeLinejoin: 'round',
  'aria-hidden': 'true',
  focusable: 'false',
};

export function PinIcon({ size = 14, filled = false }) {
  return (
    <svg {...base} width={size} height={size} fill={filled ? 'currentColor' : 'none'}>
      <line x1="12" y1="17" x2="12" y2="22" />
      <path d="M5 17h14v-1.76a2 2 0 0 0-1.11-1.79l-1.78-.9A2 2 0 0 1 15 10.76V6h1a2 2 0 0 0 0-4H8a2 2 0 0 0 0 4h1v4.76a2 2 0 0 1-1.11 1.79l-1.78.9A2 2 0 0 0 5 15.24Z" />
    </svg>
  );
}

export function ChevronsLeftIcon({ size = 14 }) {
  return (
    <svg {...base} width={size} height={size}>
      <path d="m11 17-5-5 5-5" />
      <path d="m18 17-5-5 5-5" />
    </svg>
  );
}

export function ChevronsRightIcon({ size = 14 }) {
  return (
    <svg {...base} width={size} height={size}>
      <path d="m6 17 5-5-5-5" />
      <path d="m13 17 5-5-5-5" />
    </svg>
  );
}

export function ChevronDownIcon({ size = 12 }) {
  return (
    <svg {...base} width={size} height={size}>
      <path d="m6 9 6 6 6-6" />
    </svg>
  );
}

export function ChevronRightIcon({ size = 12 }) {
  return (
    <svg {...base} width={size} height={size}>
      <path d="m9 18 6-6-6-6" />
    </svg>
  );
}

export function SearchIcon({ size = 13 }) {
  return (
    <svg {...base} width={size} height={size}>
      <circle cx="11" cy="11" r="8" />
      <path d="m21 21-4.3-4.3" />
    </svg>
  );
}

export function UnlockIcon({ size = 12 }) {
  return (
    <svg {...base} width={size} height={size}>
      <rect width="18" height="11" x="3" y="11" rx="2" ry="2" />
      <path d="M7 11V7a5 5 0 0 1 9.9-1" />
    </svg>
  );
}

export function BellIcon({ size = 14 }) {
  return (
    <svg {...base} width={size} height={size}>
      <path d="M6 8a6 6 0 0 1 12 0c0 7 3 9 3 9H3s3-2 3-9" />
      <path d="M10.3 21a1.94 1.94 0 0 0 3.4 0" />
    </svg>
  );
}

export function ClockIcon({ size = 12 }) {
  return (
    <svg {...base} width={size} height={size}>
      <circle cx="12" cy="12" r="10" />
      <polyline points="12 6 12 12 16 14" />
    </svg>
  );
}

export function SendIcon({ size = 12 }) {
  return (
    <svg {...base} width={size} height={size}>
      <path d="m22 2-7 20-4-9-9-4Z" />
      <path d="M22 2 11 13" />
    </svg>
  );
}

export function CheckIcon({ size = 12 }) {
  return (
    <svg {...base} width={size} height={size}>
      <path d="M20 6 9 17l-5-5" />
    </svg>
  );
}

export function AlertIcon({ size = 12 }) {
  return (
    <svg {...base} width={size} height={size}>
      <path d="m21.73 18-8-14a2 2 0 0 0-3.48 0l-8 14A2 2 0 0 0 4 21h16a2 2 0 0 0 1.73-3Z" />
      <line x1="12" y1="9" x2="12" y2="13" />
      <line x1="12" y1="17" x2="12.01" y2="17" />
    </svg>
  );
}

export function ActivityIcon({ size = 12 }) {
  return (
    <svg {...base} width={size} height={size}>
      <path d="M22 12h-4l-3 9L9 3l-3 9H2" />
    </svg>
  );
}

export function LayersIcon({ size = 14 }) {
  return (
    <svg {...base} width={size} height={size}>
      <path d="m12.83 2.18a2 2 0 0 0-1.66 0L2.6 6.08a1 1 0 0 0 0 1.83l8.58 3.91a2 2 0 0 0 1.66 0l8.58-3.9a1 1 0 0 0 0-1.83Z" />
      <path d="m6.08 10.37-3.49 1.59a1 1 0 0 0 0 1.83l8.59 3.9a2 2 0 0 0 1.66 0l8.58-3.9a1 1 0 0 0 0-1.83l-3.5-1.59" />
    </svg>
  );
}

export function SparkIcon({ size = 14 }) {
  return (
    <svg {...base} width={size} height={size}>
      <path d="M12 3v4M12 17v4M3 12h4M17 12h4M5.6 5.6l2.8 2.8M15.6 15.6l2.8 2.8M18.4 5.6l-2.8 2.8M8.4 15.6l-2.8 2.8" />
    </svg>
  );
}
