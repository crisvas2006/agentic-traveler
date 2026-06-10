export function formatIntelCard(type: string, data: any): { title: string; content: string; icon: string } {
  const isMissing = !data || Object.keys(data).length === 0;

  switch (type) {
    case "entry":
      return {
        title: "Visa & Entry",
        icon: "🛂",
        content: isMissing || !data.visa_rule ? "Not assessed yet." : data.visa_rule,
      };
    case "safety":
      return {
        title: "Safety",
        icon: "🛡️",
        content: isMissing || !data.summary ? "Not assessed yet." : data.summary,
      };
    case "health":
      if (isMissing) {
        return { title: "Health", icon: "🏥", content: "Not assessed yet." };
      }
      const vaccines = data?.vaccines?.length ? `Vaccines: ${data.vaccines.join(", ")}` : "Routine vaccines only.";
      const water = data?.water_safe === undefined ? "" : data.water_safe ? "Tap water is safe." : "Drink bottled water.";
      return {
        title: "Health",
        icon: "🏥",
        content: `${vaccines} ${water}`.trim(),
      };
    case "money":
      if (isMissing) {
        return { title: "Money", icon: "💵", content: "Not assessed yet." };
      }
      return {
        title: "Money",
        icon: "💵",
        content: `${data?.currency || "Local currency"}. ${data?.card_acceptance || ""} ${data?.tipping || ""}`.trim(),
      };
    case "connectivity":
      if (isMissing) {
        return { title: "Connectivity", icon: "📶", content: "Not assessed yet." };
      }
      return {
        title: "Connectivity",
        icon: "📶",
        content: `eSIM: ${data?.esim_support ? "Yes" : "No"}. ${data?.wifi_availability || ""}`,
      };
    case "climate":
      return {
        title: "Climate",
        icon: "☀️",
        content: isMissing || !data.summary ? "Not assessed yet." : data.summary,
      };
    default:
      return { title: "Intel", icon: "ℹ️", content: "Not assessed yet." };
  }
}
