"use server";

import { headers } from "next/headers";
import { createServiceClient } from "@/utils/supabase/service";
import { Resend } from "resend";
import { renderAlphaWelcomeEmail } from "@/lib/emails";
import { ALPHA_CAP } from "@/lib/alpha-config";

const resend = new Resend(process.env.RESEND_API_KEY);

const FROM_ADDRESS = process.env.RESEND_FROM_ADDRESS!;

/** Masks an email address for safe logging: "user@example.com" → "use***@example.com" */
function maskEmail(email: string): string {
  const [local, domain] = email.split("@");
  if (!domain) return "***";
  return `${local.slice(0, 3)}***@${domain}`;
}

/**
 * Early-access waitlist signup.
 *
 * Flow:
 *   1. Always insert (or detect duplicate) into `public.waitlist`.
 *   2. Compute the row's 1-indexed position by `created_at`.
 *   3. If position ≤ ALPHA_CAP → send welcome email, status='delivered'.
 *   4. If position >  ALPHA_CAP → no email, status='waitlisted', tell them their seat number.
 *
 * Uses the service-role client so RLS doesn't block status updates after the
 * email send (anonymous UPDATE on waitlist is intentionally disallowed).
 */
export async function signupForAlpha(formData: FormData) {
  const rawEmail = formData.get("email") as string | null;
  const email = rawEmail?.trim().toLowerCase() ?? "";
  if (!email) return { success: false, message: "Email is required." };

  const headersList = await headers();
  const userAgent = headersList.get("user-agent") || "unknown";
  const referer = headersList.get("referer") || "unknown";

  const supabase = createServiceClient();

  // 1. Insert (or detect duplicate)
  const { error: insertError } = await supabase
    .from("waitlist")
    .insert([{
      email,
      status: "pending",
      app_step: "alpha_version",
      user_agent: userAgent,
      referrer: referer,
    }]);

  const isDuplicate = insertError?.code === "23505";
  if (insertError && !isDuplicate) {
    console.error("[signupForAlpha] insert error:", insertError);
    return {
      success: false,
      message: "Something went sideways on our end. Try again — your email wasn't saved.",
    };
  }

  if (isDuplicate) {
    console.log("[signupForAlpha] duplicate signup for", maskEmail(email));
  }

  // 2. Find this email's row + position by created_at (1-indexed).
  const { data: row, error: rowError } = await supabase
    .from("waitlist")
    .select("created_at, status")
    .eq("email", email)
    .maybeSingle();

  if (rowError || !row) {
    console.error("[signupForAlpha] could not read row:", rowError);
    return {
      success: false,
      message: "Something went sideways on our end. Try again.",
    };
  }

  const { count, error: countError } = await supabase
    .from("waitlist")
    .select("id", { count: "exact", head: true })
    .lt("created_at", row.created_at);

  if (countError || count === null) {
    console.error("[signupForAlpha] count error:", countError);
    return {
      success: false,
      message: "Something went sideways on our end. Try again.",
    };
  }

  const position = count + 1;
  const withinCap = position <= ALPHA_CAP;

  // 3. Over cap → no email, mark waitlisted (if not already marked), return seat number.
  if (!withinCap) {
    if (row.status !== "waitlisted") {
      await supabase
        .from("waitlist")
        .update({ status: "waitlisted", updated_at: new Date().toISOString() })
        .eq("email", email);
    }
    return {
      success: true,
      message: `You're on the waitlist — seat #${position}. We'll email you when access expands.`,
    };
  }

  // 4. Within cap → send the welcome email.
  try {
    const htmlContent = await renderAlphaWelcomeEmail(email);

    const { error: emailError } = await resend.emails.send({
      from: FROM_ADDRESS,
      to: email,
      subject: "Welcome to Aletheia Travel early access 🧞‍♂️",
      html: htmlContent,
    });

    if (emailError) {
      console.error("[signupForAlpha] Resend error:", emailError);
      await supabase
        .from("waitlist")
        .update({ status: "failed", updated_at: new Date().toISOString() })
        .eq("email", email);
      return {
        success: false,
        message: "You're in — but the welcome email got stuck. We'll retry shortly.",
      };
    }

    await supabase
      .from("waitlist")
      .update({ status: "delivered", updated_at: new Date().toISOString() })
      .eq("email", email);

  } catch (err) {
    console.error("[signupForAlpha] email send failed:", err);
    await supabase
      .from("waitlist")
      .update({ status: "failed", updated_at: new Date().toISOString() })
      .eq("email", email);
    return {
      success: false,
      message: "You're in — but the welcome email got stuck. We'll retry shortly.",
    };
  }

  return {
    success: true,
    message: "You're in. Check your inbox for sign-in details — should arrive within a minute.",
  };
}
