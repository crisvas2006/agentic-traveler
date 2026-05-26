"use server";

import { headers } from "next/headers";
import { createClient } from "@/utils/supabase/server";
import { Resend } from "resend";
import { renderAlphaWelcomeEmail } from "@/lib/emails";

const resend = new Resend(process.env.RESEND_API_KEY);

const FROM_ADDRESS =
  process.env.RESEND_FROM_ADDRESS;

/** Masks an email address for safe logging: "user@example.com" → "use***@example.com" */
function maskEmail(email: string): string {
  const [local, domain] = email.split("@");
  if (!domain) return "***";
  return `${local.slice(0, 3)}***@${domain}`;
}

export async function signupForAlpha(formData: FormData) {
  const email = formData.get("email") as string;
  if (!email) return { success: false, message: "Email is required." };

  const headersList = await headers();
  const userAgent = headersList.get("user-agent") || "unknown";
  const referer = headersList.get("referer") || "unknown";

  const supabase = await createClient();

  const { error } = await supabase
    .from("waitlist")
    .insert([{
      email,
      status: "pending",
      app_step: "alpha_version",
      user_agent: userAgent,
      referrer: referer,
    }]);

  if (error) {
    if (error.code === "23505") {
      // Duplicate — proceed to resend the confirmation email.
      // Never log the raw email; masked form is safe for diagnostics.
      console.log("[signupForAlpha] duplicate signup for", maskEmail(email));
    } else {
      console.error("[signupForAlpha] insert error:", error);
      return { success: false, message: "Something went wrong. Please try again." };
    }
  }

  // Send the welcome email
  try {
    const htmlContent = await renderAlphaWelcomeEmail(email);

    const { error: emailError } = await resend.emails.send({
      from: FROM_ADDRESS,
      to: email,
      subject: "Welcome to the Aletheia Travel Alpha! 🧞‍♂️",
      html: htmlContent,
    });

    if (emailError) {
      console.error("[signupForAlpha] Resend error:", emailError);
      await supabase
        .from("waitlist")
        .update({ status: "failed", updated_at: new Date().toISOString() })
        .eq("email", email);
      return { success: false, message: "Signed up, but we couldn't send the confirmation email." };
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
    return { success: false, message: "Signed up, but we couldn't send the confirmation email." };
  }

  return { success: true, message: "Welcome to the alpha! Check your email for details." };
}
