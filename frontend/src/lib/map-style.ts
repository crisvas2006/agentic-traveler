export async function getMapStyle(theme: "light" | "dark") {
  try {
    const res = await fetch("https://tiles.openfreemap.org/styles/liberty");
    const style = await res.json();

    // The liberty style uses specific color codes. We can override them or 
    // modify layer paint properties to harmonize with our ivory/navy themes.
    const isDark = theme === "dark";
    
    const bgColor = isDark ? "#0f172a" : "#faf8f5"; // slate-900 / ivory
    const waterColor = isDark ? "#1e293b" : "#e0f2fe"; // slate-800 / sky-100
    const parkColor = isDark ? "#064e3b" : "#dcfce7"; // emerald-900 / green-100
    const roadColor = isDark ? "#334155" : "#f1f5f9"; // slate-700 / slate-100
    const textHalo = isDark ? "#0f172a" : "#faf8f5";
    const textColor = isDark ? "#f8fafc" : "#0f172a";

    // Update background
    const bgLayer = style.layers.find((l: { type: string; paint: Record<string, string> }) => l.type === "background");
    if (bgLayer) {
      bgLayer.paint["background-color"] = bgColor;
    }

    // Modify other layers
    for (const layer of style.layers) {
      if (layer.id.includes("water") && layer.type === "fill" && layer.paint) {
        layer.paint["fill-color"] = waterColor;
      }
      if (layer.id.includes("park") || layer.id.includes("wood") || layer.id.includes("forest") || layer.id.includes("grass") || layer.id.includes("pitch")) {
        if (layer.type === "fill" && layer.paint) {
          layer.paint["fill-color"] = parkColor;
        }
      }
      if (layer.id.includes("road") || layer.id.includes("highway")) {
        if (layer.type === "line" && layer.paint && layer.paint["line-color"]) {
          layer.paint["line-color"] = roadColor;
        }
      }
      if (layer.type === "symbol" && layer.paint && layer.paint["text-halo-color"]) {
        layer.paint["text-halo-color"] = textHalo;
        layer.paint["text-color"] = textColor;
      }
      if (layer.type === "symbol" && layer.paint && layer.paint["text-halo-width"]) {
        layer.paint["text-halo-width"] = 2; // Make labels clearer
      }
    }

    return style;
  } catch (error) {
    console.error("Failed to load/modify map style", error);
    // Fallback if fetch fails (should not happen normally)
    return "https://tiles.openfreemap.org/styles/liberty";
  }
}
