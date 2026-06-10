"use client";

import { useCallback, useEffect, useMemo, useState } from "react";

import { createClient } from "@/utils/supabase/client";
import { useTripRealtime } from "@/hooks/useTripRealtime";
import { adaptTrip, adaptSummary } from "@/lib/trip-adapter";
import type { Trip, TripDay, TripSummary } from "@/lib/dashboard-data";

/**
 * useTrip (Task 40) — the dashboard's composition hook.
 *
 * Wraps `useTripRealtime` (which owns the parent-row subscription + child
 * refetch) and runs the raw assembled trip through `adaptTrip` into the
 * `Trip` + `TripDay[]` view model the panel components consume. Adds a
 * coarse 60s poll as a fallback for a dropped Realtime socket (spec §6).
 */
export function useTrip(tripId: string | null): {
  trip: Trip | null;
  days: TripDay[];
  todayN: number;
  loading: boolean;
  refetch: () => void;
} {
  const { trip: raw, loading, refetch } = useTripRealtime(tripId);

  // Fallback poll: if the Realtime socket silently drops, a 60s refetch keeps
  // the panel from going stale. Cheap (one assembled-trip fetch/minute) and
  // only while a trip is open.
  useEffect(() => {
    if (!tripId) return;
    const id = setInterval(() => void refetch(), 60_000);
    return () => clearInterval(id);
  }, [tripId, refetch]);

  const adapted = useMemo(() => adaptTrip(raw), [raw]);

  return {
    trip: adapted?.trip ?? null,
    days: adapted?.days ?? [],
    todayN: adapted?.todayN ?? 1,
    loading,
    refetch,
  };
}

/**
 * useTripList (Task 40) — the user's trips for the library, RLS-scoped.
 *
 * Reads through the browser Supabase client so the user only ever sees their
 * own trips (AC-8). Picks a sensible default active trip: an `active` trip
 * first, otherwise the most-recently updated. The active id is owned by the
 * caller (DashboardShell) so trip switching stays a pure UI concern.
 */
export function useTripList(): {
  summaries: TripSummary[];
  defaultActiveId: string | null;
  loading: boolean;
  refetch: () => void;
} {
  const [summaries, setSummaries] = useState<TripSummary[]>([]);
  const [defaultActiveId, setDefaultActiveId] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);

  const refetch = useCallback(async () => {
    const supabase = createClient();
    setLoading(true);
    try {
      const { data } = await supabase
        .from("trips")
        .select("*, trip_destinations(name,iso_country,ord,status)")
        .order("updated_at", { ascending: false });
      const rows = (data ?? []) as Record<string, unknown>[];
      const mapped = rows.map(adaptSummary);
      setSummaries(mapped);
      // Default focus: an active trip wins; else the most recent (rows are
      // already updated_at-desc).
      const active = mapped.find((m) => m.status === "active");
      setDefaultActiveId(active?.id ?? mapped[0]?.id ?? null);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    // Initial load. Standard fetch-in-effect (mirrors useTripRealtime); the
    // loading flag it flips is intentional, not a cascading-render bug.
    // eslint-disable-next-line react-hooks/set-state-in-effect
    void refetch();
  }, [refetch]);

  return { summaries, defaultActiveId, loading, refetch };
}
