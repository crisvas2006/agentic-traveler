"use server";

import * as React from "react";
import { headers } from "next/headers";
import { createClient } from "@/utils/supabase/server";
import { Resend } from "resend";
import { render } from "@react-email/components";
import { AlphaWelcomeEmail } from "@/emails/AlphaWelcomeEmail";

const resend = new Resend(process.env.RESEND_API_KEY);

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
      status: 'pending',
      app_step: 'alpha_version',
      user_agent: userAgent,
      referrer: referer
    }]);

  if (error) {
    if (error.code === '23505') {
      // User is already in the database.
      // We skip the error and proceed to send the email and update their row.
      console.log(`Duplicate signup for ${email}, proceeding to resend email.`);
    } else {
      console.error("Error signing up:", error);
      return { success: false, message: "Something went wrong. Please try again." };
    }
  }

  // Send the welcome email
  try {
    const htmlContent = await render(<AlphaWelcomeEmail email={email} />);

    const { data: emailData, error: emailError } = await resend.emails.send({
      from: "Aletheia Travel <noreply@contact.aletheiatravel.eu>", // Resend testing email since no custom domain is verified yet
      to: email,
      subject: "Welcome to the Aletheia Travel Alpha! 🧞‍♂️",
      html: htmlContent,
    });

    if (emailError) {
      console.error("Resend error:", emailError);
      // Try to update status to failed
      await supabase.from("waitlist").update({ status: 'failed', updated_at: new Date().toISOString() }).eq("email", email);
      return { success: false, message: "Signed up, but we couldn't send the confirmation email." };
    }

    // Update status to delivered upon successful email send
    await supabase.from("waitlist").update({ status: 'delivered', updated_at: new Date().toISOString() }).eq("email", email);

  } catch (err) {
    console.error("Failed to send email:", err);
    // Try to update status to failed
    await supabase.from("waitlist").update({ status: 'failed', updated_at: new Date().toISOString() }).eq("email", email);
    return { success: false, message: "Signed up, but we couldn't send the confirmation email." };
  }

  return { success: true, message: "Welcome to the alpha! Check your email for details." };
}
