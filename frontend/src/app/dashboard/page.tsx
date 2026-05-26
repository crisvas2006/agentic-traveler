import { redirect } from "next/navigation";
import { createClient } from "@/utils/supabase/server";
import { DashboardShell } from "@/components/dashboard/DashboardShell";

/**
 * Defense-in-depth auth check.
 * The middleware (proxy.ts) already redirects unauthenticated visitors, but
 * a server-component check here ensures the page never renders for an
 * unauthenticated user even if middleware misconfigures or is bypassed.
 */
export default async function DashboardPage() {
  const supabase = await createClient();
  const {
    data: { user },
  } = await supabase.auth.getUser();

  if (!user) {
    redirect("/login");
  }

  return <DashboardShell />;
}
