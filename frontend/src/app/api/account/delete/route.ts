import { NextResponse } from "next/server";
import { createClient } from "@/utils/supabase/server";
import { createServiceClient } from "@/utils/supabase/service";

export async function POST(request: Request) {
  // Origin guard
  const siteUrl = process.env.NEXT_PUBLIC_SITE_URL;
  if (siteUrl) {
    const origin = request.headers.get("origin");
    if (origin && origin !== siteUrl) {
      return NextResponse.json({ error: "Forbidden" }, { status: 403 });
    }
  }

  // Auth required — confirm the session is valid before deleting
  const supabase = await createClient();
  const { data: { user } } = await supabase.auth.getUser();
  if (!user) return NextResponse.json({ error: "Unauthorized" }, { status: 401 });

  const svc = createServiceClient();

  // Delete from auth.users — CASCADE handles public.users + all child rows
  const { error } = await svc.auth.admin.deleteUser(user.id);
  if (error) {
    console.error("[account/delete] deleteUser error:", error);
    return NextResponse.json({ error: "Failed to delete account. Please try again." }, { status: 500 });
  }

  // Sign the session out (best-effort — the auth row is already gone)
  await supabase.auth.signOut();

  return NextResponse.json({ success: true });
}
