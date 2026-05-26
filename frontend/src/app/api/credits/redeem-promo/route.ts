import { NextResponse } from "next/server";
import { createClient } from "@/utils/supabase/server";
import { createServiceClient } from "@/utils/supabase/service";
import { PROMO_CODES } from "@/lib/promo-codes";

// Mirror of backend/src/agentic_traveler/economy/promo_codes.py
const VALID_CODES = PROMO_CODES;

export async function POST(request: Request) {
  // Origin guard
  const siteUrl = process.env.NEXT_PUBLIC_SITE_URL;
  if (siteUrl) {
    const origin = request.headers.get("origin");
    if (origin && origin !== siteUrl) {
      return NextResponse.json({ error: "Forbidden" }, { status: 403 });
    }
  }

  // Auth required
  const supabase = await createClient();
  const { data: { user } } = await supabase.auth.getUser();
  if (!user) return NextResponse.json({ error: "Unauthorized" }, { status: 401 });

  const body = await request.json().catch(() => ({}));
  const code = String(body?.code ?? "").trim().toUpperCase();
  if (!code) return NextResponse.json({ error: "Code is required." }, { status: 400 });

  const creditsToAdd = VALID_CODES[code];
  if (creditsToAdd === undefined) {
    return NextResponse.json(
      { error: "Code not recognized. Check spelling or try another." },
      { status: 400 }
    );
  }

  // Resolve internal user_id
  const { data: userRow } = await supabase.from("users").select("id").maybeSingle();
  if (!userRow) return NextResponse.json({ error: "User record not found." }, { status: 404 });

  const svc = createServiceClient();

  // Fetch current credits row (service role bypasses RLS write restriction)
  const { data: cred, error: credErr } = await svc
    .from("credits")
    .select("balance, used_promos")
    .eq("user_id", userRow.id)
    .maybeSingle();

  if (credErr) {
    console.error("[redeem-promo] credits fetch:", credErr);
    return NextResponse.json({ error: "Could not verify promo eligibility." }, { status: 500 });
  }

  const usedPromos: string[] = cred?.used_promos ?? [];
  if (usedPromos.includes(code)) {
    return NextResponse.json(
      { error: "This code has already been applied to your account." },
      { status: 400 }
    );
  }

  // Atomically apply
  const { error: updateErr } = await svc
    .from("credits")
    .update({
      balance: (cred?.balance ?? 0) + creditsToAdd,
      used_promos: [...usedPromos, code],
    })
    .eq("user_id", userRow.id);

  if (updateErr) {
    console.error("[redeem-promo] update:", updateErr);
    return NextResponse.json({ error: "Failed to apply promo code." }, { status: 500 });
  }

  return NextResponse.json({
    success: true,
    message: `+${creditsToAdd} credits added to your balance!`,
    creditsAdded: creditsToAdd,
  });
}
