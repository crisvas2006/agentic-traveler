"use client";

import { useState } from "react";
import { SparklesIcon } from "./DashIcons";

interface WelcomeGrantModalProps {
  /** Called with the actual balance after a successful claim */
  onGranted: (balance: number) => void;
  /** Called when the user dismisses the modal without claiming */
  onDismiss: () => void;
}

export function WelcomeGrantModal({ onGranted, onDismiss }: WelcomeGrantModalProps) {
  const [status, setStatus] = useState<"idle" | "loading" | "error">("idle");
  const [errorMsg, setErrorMsg] = useState("");

  const handleClaim = async () => {
    setStatus("loading");
    setErrorMsg("");

    try {
      const res = await fetch("/api/credits/welcome-grant", { method: "POST" });

      // Guard against empty / non-JSON responses (e.g. unhandled server crash)
      let body: { status?: "granted" | "already_claimed"; balance?: number; error?: string };
      try {
        body = await res.json();
      } catch (parseErr) {
        console.error("[WelcomeGrantModal] non-JSON response:", res.status, parseErr);
        throw new Error("Server returned an unexpected response.");
      }

      if (!res.ok) {
        // Log the technical reason; show a generic message to the user
        console.error("[WelcomeGrantModal] grant failed:", res.status, body.error);
        throw new Error("grant_failed");
      }

      if (body.status === "granted" && typeof body.balance === "number") {
        onGranted(body.balance);
      } else if (body.status === "already_claimed") {
        // Claimed in another tab — just close the modal
        onGranted(-1);
      } else {
        console.error("[WelcomeGrantModal] unexpected body:", body);
        throw new Error("grant_failed");
      }
    } catch (err) {
      setStatus("error");
      // Only surface a generic message — technical details are in the console
      const msg = err instanceof Error ? err.message : "";
      setErrorMsg(
        msg === "grant_failed" || msg === "Server returned an unexpected response."
          ? "Something went sideways on our end. Try again — your credits are safe."
          : "Something went sideways. Try again."
      );
    }
  };

  return (
    /* Full-viewport overlay — click backdrop OR X to dismiss */
    <div
      className="fixed inset-0 z-[100] flex items-center justify-center p-4"
      style={{ background: "rgba(0,0,0,0.55)", backdropFilter: "blur(6px)" }}
      onClick={onDismiss}
    >
      {/* Stop propagation so clicks inside the card don't bubble to the backdrop */}
      <div
        className="relative w-full max-w-sm rounded-[2rem] border border-border overflow-hidden animate-fade-up"
        style={{ background: "var(--background)" }}
        onClick={(e) => e.stopPropagation()}
      >
        {/* Dismiss button */}
        <button
          type="button"
          onClick={onDismiss}
          aria-label="Dismiss"
          className="absolute top-4 right-4 w-8 h-8 rounded-full grid place-items-center text-muted-foreground hover:text-foreground hover:bg-foreground/8 transition-colors z-10"
        >
          <svg viewBox="0 0 16 16" width={14} height={14} fill="none" stroke="currentColor" strokeWidth={2} strokeLinecap="round">
            <path d="M3 3l10 10M13 3L3 13" />
          </svg>
        </button>

        {/* Gradient header */}
        <div
          className="px-8 pt-10 pb-8 flex flex-col items-center text-center"
          style={{
            background:
              "linear-gradient(160deg, color-mix(in oklab, var(--primary) 12%, transparent), color-mix(in oklab, #9333ea 8%, transparent))",
          }}
        >
          <div
            className="w-16 h-16 rounded-2xl grid place-items-center mb-5"
            style={{
              background: "linear-gradient(135deg, var(--primary), #9333ea)",
              boxShadow: "0 16px 40px -10px color-mix(in oklab, var(--primary) 60%, transparent)",
            }}
          >
            <SparklesIcon width={28} height={28} className="text-white" />
          </div>

          <h2 className="text-2xl font-extrabold tracking-tight leading-tight mb-2">
            Welcome to Aletheia
          </h2>
          <p className="text-sm text-muted-foreground leading-relaxed">
            Thanks for joining. Here&rsquo;s a starter pack of credits so you can plan your first trip - on us.
          </p>
        </div>

        {/* Body */}
        <div className="px-8 pb-8 pt-6">
          {/* Feature bullets */}
          <ul className="space-y-2.5 mb-7">
            {[
              "Chat with your travel companion",
              "Build itineraries shaped by your Traveler DNA",
              "Adapt your plans in real time",
            ].map((item) => (
              <li key={item} className="flex items-center gap-2.5 text-sm text-foreground/80">
                <span
                  className="w-5 h-5 rounded-full grid place-items-center flex-shrink-0"
                  style={{
                    background: "color-mix(in oklab, var(--primary) 14%, transparent)",
                  }}
                >
                  <svg
                    viewBox="0 0 12 12"
                    width={10}
                    height={10}
                    fill="none"
                    stroke="var(--primary)"
                    strokeWidth={2}
                    strokeLinecap="round"
                    strokeLinejoin="round"
                  >
                    <path d="M2 6l2.5 2.5L10 3.5" />
                  </svg>
                </span>
                {item}
              </li>
            ))}
          </ul>

          {/* CTA */}
          <button
            type="button"
            onClick={handleClaim}
            disabled={status === "loading"}
            className="w-full h-12 rounded-full font-semibold text-base text-white transition-all disabled:opacity-60 disabled:cursor-not-allowed flex items-center justify-center gap-2"
            style={{
              background: "linear-gradient(135deg, var(--primary), #9333ea)",
              boxShadow: "0 8px 24px -6px color-mix(in oklab, var(--primary) 50%, transparent)",
            }}
          >
            {status === "loading" ? (
              <>
                <svg
                  className="animate-spin"
                  width={16}
                  height={16}
                  viewBox="0 0 24 24"
                  fill="none"
                  stroke="currentColor"
                  strokeWidth={2.5}
                >
                  <path d="M21 12a9 9 0 1 1-3-6.7" strokeLinecap="round" />
                </svg>
                <span>Claiming…</span>
              </>
            ) : (
              <span>Claim my credits →</span>
            )}
          </button>

          {/* Error feedback */}
          {status === "error" && (
            <p className="mt-3 text-xs text-center text-rose-500 dark:text-rose-400 animate-fade-up">
              {errorMsg}
            </p>
          )}
        </div>
      </div>
    </div>
  );
}
