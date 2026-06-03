import { redirect } from "next/navigation";
import { createClient } from "@/utils/supabase/server";
import { AccountSettings } from "@/components/settings/AccountSettings";

export const metadata = { title: "Account Settings — Aletheia Travel" };

export default async function SettingsPage() {
  const supabase = await createClient();
  const { data: { user } } = await supabase.auth.getUser();
  if (!user) redirect("/login");

  let botUsername = process.env.TELEGRAM_BOT_USERNAME || "";
  if (!botUsername) {
    throw new Error("Missing required environment variable: TELEGRAM_BOT_USERNAME");
  }

  if (botUsername.startsWith("@")) {
    botUsername = botUsername.substring(1);
  }

  return <AccountSettings botUsername={botUsername} />;
}
