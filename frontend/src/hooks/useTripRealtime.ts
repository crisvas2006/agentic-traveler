"use client";

import { useCallback, useEffect, useState } from "react";

import { createClient } from "@/utils/supabase/client";

/**
 * useTripRealtime (Task 37) — live view of a single trip.
 *
 * Subscribes to UPDATEs on the parent `trips` row (one WebSocket channel) and
 * refetches the assembled trip — parent + the five child collections — on every
 * change. Because a Postgres trigger bumps `trips.updated_at` whenever a child
 * row changes, this single parent subscription reflects child writes too.
 * Reads go through the RLS-protected browser client, so the user only ever sees
 * their own trip.
 *
 * Consumed by the Trip Detail Panel (task 40); shipped here as the data
 * primitive task 37 owns.
 */

export type Trip = Record<string, unknown> & {
  id: string;
  destinations: Record<string, unknown>[];
  bookings: Record<string, unknown>[];
  days: Record<string, unknown>[];
  day_blocks: Record<string, unknown>[];
  checklist: Record<string, unknown>[];
};

export function useTripRealtime(tripId: string | null) {
  const [trip, setTrip] = useState<Trip | null>(null);
  const [loading, setLoading] = useState(false);

  const refetch = useCallback(async () => {
    if (!tripId) {
      setTrip(null);
      return;
    }
    const supabase = createClient();
    setLoading(true);
    try {
      const [parent, dests, bookings, days, blocks, checklist] = await Promise.all([
        supabase.from("trips").select("*").eq("id", tripId).maybeSingle(),
        supabase.from("trip_destinations").select("*").eq("trip_id", tripId).order("ord"),
        supabase.from("trip_bookings").select("*").eq("trip_id", tripId).order("datetime_local"),
        supabase.from("trip_days").select("*").eq("trip_id", tripId).order("n"),
        supabase.from("trip_day_blocks").select("*").eq("trip_id", tripId).order("ord"),
        supabase.from("trip_checklist").select("*").eq("trip_id", tripId).order("ord"),
      ]);
      if (!parent.data) {
        setTrip(null);
        return;
      }
      setTrip({
        ...(parent.data as Record<string, unknown>),
        id: tripId,
        destinations: dests.data ?? [],
        bookings: bookings.data ?? [],
        days: days.data ?? [],
        day_blocks: blocks.data ?? [],
        checklist: checklist.data ?? [],
      });
    } finally {
      setLoading(false);
    }
  }, [tripId]);

  useEffect(() => {
    // Kick off the initial fetch (it also resets to null when tripId is
    // absent). This is the standard fetch-in-effect pattern; the loading flag
    // it flips is intentional, not a cascading-render bug.
    // eslint-disable-next-line react-hooks/set-state-in-effect
    void refetch();
    if (!tripId) return;

    const supabase = createClient();
    const channel = supabase
      .channel(`trip:${tripId}`)
      .on(
        "postgres_changes",
        { event: "UPDATE", schema: "public", table: "trips", filter: `id=eq.${tripId}` },
        () => {
          void refetch();
        },
      )
      .subscribe();

    return () => {
      void supabase.removeChannel(channel);
    };
  }, [tripId, refetch]);

  return { trip, loading, refetch };
}
