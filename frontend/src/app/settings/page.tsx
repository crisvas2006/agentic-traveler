import { redirect } from "next/navigation";
import { createClient } from "@/utils/supabase/server";
import { AccountSettings } from "@/components/settings/AccountSettings";

export const metadata = { title: "Account Settings — Aletheia Travel" };

export default async function SettingsPage() {
  const supabase = await createClient();
  const { data: { user } } = await supabase.auth.getUser();
  if (!user) redirect("/login");

  return <AccountSettings />;
}
