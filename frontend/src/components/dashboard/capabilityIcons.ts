// capabilityIcons.ts — maps a registry `icon` name (lucide-react export name,
// stored as a string in capabilities.ts so that module stays pure data) to its
// lucide component. Shared by the launcher sheet, the chips, and the manual page.

import {
  Compass,
  Map as MapIcon,
  ShieldCheck,
  CloudSun,
  Ticket,
  Smile,
  RefreshCw,
  BookOpen,
  SlidersHorizontal,
  Send,
  Gift,
  Sparkles,
  type LucideIcon,
} from "lucide-react";

const ICONS: Record<string, LucideIcon> = {
  Compass,
  Map: MapIcon,
  ShieldCheck,
  CloudSun,
  Ticket,
  Smile,
  RefreshCw,
  BookOpen,
  SlidersHorizontal,
  Send,
  Gift,
  Sparkles,
};

/** Resolve a registry icon name to its lucide component (Sparkles fallback). */
export function capabilityIcon(name: string): LucideIcon {
  return ICONS[name] ?? Sparkles;
}
