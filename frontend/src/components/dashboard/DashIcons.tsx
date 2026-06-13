import type { SVGProps } from "react";

type IconProps = SVGProps<SVGSVGElement>;

const iconBase: IconProps = {
  viewBox: "0 0 24 24",
  fill: "none",
  stroke: "currentColor",
  strokeWidth: 2,
  strokeLinecap: "round" as const,
  strokeLinejoin: "round" as const,
};

export function SparklesIcon(p: IconProps) {
  return (
    <svg {...iconBase} {...p}>
      <path d="M12 3v4M12 17v4M3 12h4M17 12h4M5.6 5.6l2.8 2.8M15.6 15.6l2.8 2.8M5.6 18.4l2.8-2.8M15.6 8.4l2.8-2.8" />
    </svg>
  );
}

export function BellIcon(p: IconProps) {
  return (
    <svg {...iconBase} {...p}>
      <path d="M6 8a6 6 0 0 1 12 0c0 7 3 9 3 9H3s3-2 3-9" />
      <path d="M10 21a2 2 0 0 0 4 0" />
    </svg>
  );
}

export function PlusIcon(p: IconProps) {
  return (
    <svg {...iconBase} strokeWidth={2.5} {...p}>
      <path d="M12 5v14M5 12h14" />
    </svg>
  );
}

export function ChatIcon(p: IconProps) {
  return (
    <svg {...iconBase} {...p}>
      <path d="M21 12a8 8 0 0 1-11.6 7.2L4 21l1.8-5A8 8 0 1 1 21 12Z" />
    </svg>
  );
}

export function SendIcon(p: IconProps) {
  return (
    <svg {...iconBase} {...p}>
      <path d="M22 2 11 13M22 2l-7 20-4-9-9-4 20-7Z" />
    </svg>
  );
}

export function ChevronDownIcon(p: IconProps) {
  return (
    <svg {...iconBase} {...p}>
      <path d="m6 9 6 6 6-6" />
    </svg>
  );
}

export function ChevronRightIcon(p: IconProps) {
  return (
    <svg {...iconBase} {...p}>
      <path d="m9 6 6 6-6 6" />
    </svg>
  );
}

export function MapIcon(p: IconProps) {
  return (
    <svg {...iconBase} {...p}>
      <path d="M9 4 3 6v14l6-2 6 2 6-2V4l-6 2-6-2Z" />
      <path d="M9 4v14M15 6v14" />
    </svg>
  );
}

export function LibraryIcon(p: IconProps) {
  return (
    <svg {...iconBase} {...p}>
      <rect x="3" y="4" width="6" height="16" rx="1" />
      <rect x="11" y="4" width="6" height="16" rx="1" />
      <path d="M19 6.5v11" />
    </svg>
  );
}

export function DNAIcon(p: IconProps) {
  return (
    <svg {...iconBase} {...p}>
      <path d="M4 2c0 6 16 8 16 14M4 8c0 6 16 8 16 14M4 22c0-6 16-8 16-14" />
    </svg>
  );
}

export function RainIcon(p: IconProps) {
  return (
    <svg {...iconBase} {...p}>
      <path d="M16 14a4 4 0 1 0 0-8 6 6 0 0 0-11.7 1.8A4 4 0 0 0 6 14" />
      <path d="M8 19v2M12 18v3M16 19v2" />
    </svg>
  );
}

export function WalkIcon(p: IconProps) {
  return (
    <svg {...iconBase} {...p}>
      <circle cx="13" cy="4" r="2" />
      <path d="m9 21 2-6-3-3 3-5 4 2 3 3M6 14l2 3 1 4" />
    </svg>
  );
}

export function ClockIcon(p: IconProps) {
  return (
    <svg {...iconBase} {...p}>
      <circle cx="12" cy="12" r="10" />
      <path d="M12 6v6l4 2" />
    </svg>
  );
}

export function RefreshIcon(p: IconProps) {
  return (
    <svg {...iconBase} {...p}>
      <path d="M21 12a9 9 0 1 1-3-6.7L21 8" />
      <path d="M21 3v5h-5" />
    </svg>
  );
}

export function SettingsIcon(p: IconProps) {
  return (
    <svg {...iconBase} {...p}>
      <circle cx="12" cy="12" r="3" />
      <path d="M19.4 15a1.65 1.65 0 0 0 .33 1.82l.06.06a2 2 0 0 1-2.83 2.83l-.06-.06a1.65 1.65 0 0 0-1.82-.33 1.65 1.65 0 0 0-1 1.51V21a2 2 0 0 1-4 0v-.09A1.65 1.65 0 0 0 9 19.4a1.65 1.65 0 0 0-1.82.33l-.06.06a2 2 0 0 1-2.83-2.83l.06-.06A1.65 1.65 0 0 0 4.68 15a1.65 1.65 0 0 0-1.51-1H3a2 2 0 0 1 0-4h.09A1.65 1.65 0 0 0 4.6 9a1.65 1.65 0 0 0-.33-1.82l-.06-.06a2 2 0 0 1 2.83-2.83l.06.06A1.65 1.65 0 0 0 9 4.68a1.65 1.65 0 0 0 1-1.51V3a2 2 0 0 1 4 0v.09a1.65 1.65 0 0 0 1 1.51 1.65 1.65 0 0 0 1.82-.33l.06-.06a2 2 0 0 1 2.83 2.83l-.06.06A1.65 1.65 0 0 0 19.4 9a1.65 1.65 0 0 0 1.51 1H21a2 2 0 0 1 0 4h-.09a1.65 1.65 0 0 0-1.51 1Z" />
    </svg>
  );
}

export function CreditIcon(p: IconProps) {
  return (
    <svg {...iconBase} {...p}>
      <rect x="2" y="5" width="20" height="14" rx="2" />
      <path d="M2 10h20" />
    </svg>
  );
}

export function SunIcon(p: IconProps) {
  return (
    <svg {...iconBase} {...p}>
      <circle cx="12" cy="12" r="4" />
      <path d="M12 2v2M12 20v2M4.9 4.9l1.4 1.4M17.7 17.7l1.4 1.4M2 12h2M20 12h2M4.9 19.1l1.4-1.4M17.7 6.3l1.4-1.4" />
    </svg>
  );
}

export function MoonIcon(p: IconProps) {
  return (
    <svg {...iconBase} {...p}>
      <path d="M21 12.8A9 9 0 1 1 11.2 3a7 7 0 0 0 9.8 9.8Z" />
    </svg>
  );
}

export function HelpIcon(p: IconProps) {
  return (
    <svg {...iconBase} {...p}>
      <circle cx="12" cy="12" r="10" />
      <path d="M9.1 9a3 3 0 0 1 5.82 1c0 2-3 3-3 3" />
      <path d="M12 17h.01" strokeWidth={2.5} />
    </svg>
  );
}

export function LogOutIcon(p: IconProps) {
  return (
    <svg {...iconBase} {...p}>
      <path d="M9 21H5a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h4" />
      <polyline points="16 17 21 12 16 7" />
      <line x1="21" y1="12" x2="9" y2="12" />
    </svg>
  );
}

export function CheckIcon(p: IconProps) {
  return (
    <svg {...iconBase} strokeWidth={2.5} {...p}>
      <path d="M20 6 9 17l-5-5" />
    </svg>
  );
}

export function MapPinIcon(p: IconProps) {
  return (
    <svg {...iconBase} {...p}>
      <path d="M20 10c0 6-8 12-8 12s-8-6-8-12a8 8 0 0 1 16 0Z" />
      <circle cx="12" cy="10" r="3" />
    </svg>
  );
}

export function XIcon(p: IconProps) {
  return (
    <svg {...iconBase} strokeWidth={2.5} {...p}>
      <path d="M18 6 6 18M6 6l12 12" />
    </svg>
  );
}
