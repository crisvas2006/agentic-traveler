import { redirect } from "next/navigation";
import { createClient } from "@/utils/supabase/server";
import { CapabilityGuide } from "@/components/guide/CapabilityGuide";

// Defense-in-depth: server-component auth check mirrors dashboard/page.tsx.
export default async function GuidePage() {
  const supabase = await createClient();
  const {
    data: { user },
  } = await supabase.auth.getUser();

  if (!user) redirect("/login");

  return <CapabilityGuide />;
}
