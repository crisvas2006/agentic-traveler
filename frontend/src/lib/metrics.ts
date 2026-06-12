// metrics.ts — fire-and-forget client metric emit (Task 50).
//
// The browser cannot write to analytics_events directly (no service key on the
// client). This posts an allowlisted event name to the Next route handler, which
// proxies it to the backend with the user's session. Failures are swallowed —
// analytics must never disrupt the UI.

export function track(name: string, props?: Record<string, unknown>): void {
  try {
    void fetch("/api/metrics", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ name, props: props ?? {} }),
      keepalive: true,
    }).catch(() => {});
  } catch {
    // Never throw from a metric emit.
  }
}
