"use client";

import { useEffect, useState } from "react";
import { createClient } from "@/utils/supabase/client";

export interface UserProfile {
  name: string;
  email: string;
  initials: string;
  dnaTags: string[];
  balance: number;
  initialGrant: number;
  /** null = not yet claimed → may show modal. undefined = fetch failed/unknown → never show modal. */
  welcomeClaimedAt: string | null | undefined;
  loading: boolean;
  /** true if the profile query itself failed (e.g. permissions, network) */
  fetchError: boolean;
}

const EMPTY: UserProfile = {
  name: "",
  email: "",
  initials: "…",
  dnaTags: [],
  balance: 0,
  initialGrant: 0,
  welcomeClaimedAt: undefined, // unknown until loaded
  loading: true,
  fetchError: false,
};

function deriveInitials(name: string): string {
  return (
    name
      .split(/\s+/)
      .filter(Boolean)
      .slice(0, 2)
      .map((w) => w[0].toUpperCase())
      .join("") || "?"
  );
}

export function useUserProfile(): UserProfile {
  const [profile, setProfile] = useState<UserProfile>(EMPTY);

  useEffect(() => {
    let cancelled = false;

    async function load() {
      const supabase = createClient();

      const {
        data: { user },
        error: authErr,
      } = await supabase.auth.getUser();

      if (authErr || !user) {
        if (!cancelled) setProfile({ ...EMPTY, loading: false });
        return;
      }

      const email = user.email ?? "";

      // ── Two parallel queries ────────────────────────────────────────────────
      // Credits are queried separately (not embedded) because PostgREST can
      // silently return empty for embedded resources whose RLS policy
      // subqueries the same parent table being read in the outer query.
      // A direct top-level SELECT works correctly with the same RLS policy.
      const [usersResult, creditsResult] = await Promise.all([
        supabase
          .from("users")
          .select("name, user_profiles ( profile_data )")
          .maybeSingle(),
        supabase
          .from("credits")
          .select("balance, initial_grant, welcome_credits_claimed_at")
          .maybeSingle(),
      ]);

      if (cancelled) return;

      if (usersResult.error) {
        console.error("[useUserProfile] users query failed:", usersResult.error);
        setProfile({ ...EMPTY, email, loading: false, fetchError: true });
        return;
      }

      if (!usersResult.data) {
        // No public.users row yet (trigger may not have fired)
        setProfile({ ...EMPTY, email, loading: false });
        return;
      }

      const profileRows = usersResult.data.user_profiles as
        | Array<{ profile_data: { tags?: string[] } | null }>
        | null;
      const profileRow = profileRows?.[0];
      const name = usersResult.data.name || email.split("@")[0] || "Traveler";

      const credits = creditsResult.data;

      if (creditsResult.error) {
        console.error("[useUserProfile] credits query failed:", creditsResult.error);
      }

      // If credits could not be fetched (null data or error), treat
      // welcomeClaimedAt as undefined so we never wrongly show or hide the modal.
      const welcomeClaimedAt =
        credits != null
          ? credits.welcome_credits_claimed_at  // null = unclaimed → show modal
          : undefined;                           // no row / error → unknown

      setProfile({
        name,
        email,
        initials: deriveInitials(name),
        dnaTags: profileRow?.profile_data?.tags ?? [],
        balance: credits?.balance ?? 0,
        initialGrant: credits?.initial_grant ?? 0,
        welcomeClaimedAt,
        loading: false,
        fetchError: usersResult.error != null,
      });
    }

    load();
    return () => {
      cancelled = true;
    };
  }, []);

  return profile;
}
