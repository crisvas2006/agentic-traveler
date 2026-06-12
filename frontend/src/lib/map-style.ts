export async function getMapStyle(theme: "light" | "dark") {
  try {
    const res = await fetch("https://tiles.openfreemap.org/styles/liberty");
    const style = await res.json();
    return style;
  } catch (error) {
    console.error("Failed to load map style", error);
    // Fallback if fetch fails
    return "https://tiles.openfreemap.org/styles/liberty";
  }
}
