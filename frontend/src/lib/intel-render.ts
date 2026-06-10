export function formatIntelCard(type: string, data: any): { title: string; content: string; icon: string } {
  switch (type) {
    case "entry":
      return {
        title: "Visa & Entry",
        icon: "🛂",
        content: data?.visa_rule || "Unknown",
      };
    case "safety":
      return {
        title: "Safety",
        icon: "🛡️",
        content: data?.summary || "No specific warnings.",
      };
    case "health":
      const vaccines = data?.vaccines?.length ? `Vaccines: ${data.vaccines.join(", ")}` : "Routine vaccines only.";
      const water = data?.water_safe ? "Tap water is safe." : "Drink bottled water.";
      return {
        title: "Health",
        icon: "🏥",
        content: `${vaccines} ${water}`,
      };
    case "money":
      return {
        title: "Money",
        icon: "💵",
        content: `${data?.currency || "Local currency"}. ${data?.card_acceptance || ""} ${data?.tipping || ""}`,
      };
    case "connectivity":
      return {
        title: "Connectivity",
        icon: "📶",
        content: `eSIM: ${data?.esim_support ? "Yes" : "No"}. ${data?.wifi_availability || ""}`,
      };
    case "climate":
      return {
        title: "Climate",
        icon: "☀️",
        content: `${data?.summary || ""}`,
      };
    default:
      return { title: "Intel", icon: "ℹ️", content: "..." };
  }
}
