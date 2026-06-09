"use client";

import React, { useState, useEffect, useRef, useCallback } from "react";
import { createClient } from "@/utils/supabase/client";
import { SparklesIcon, CheckIcon, ChevronRightIcon } from "@/components/dashboard/DashIcons";
import type { SVGProps } from "react";
import Link from "next/link";

/* ── Tiny icon helpers ────────────────────────────────────────────────── */
type IP = SVGProps<SVGSVGElement>;
const base: IP = { viewBox: "0 0 24 24", fill: "none", stroke: "currentColor", strokeWidth: 2, strokeLinecap: "round" as const, strokeLinejoin: "round" as const };

function BackIcon(p: IP) { return <svg {...base} {...p}><path d="m15 18-6-6 6-6" /></svg>; }
function PencilIcon(p: IP) { return <svg {...base} {...p}><path d="M12 20h9" /><path d="M16.5 3.5a2.121 2.121 0 1 1 3 3L7 19l-4 1 1-4Z" /></svg>; }
function XIcon(p: IP) { return <svg {...base} {...p}><path d="M18 6 6 18M6 6l12 12" /></svg>; }
function PlusIcon(p: IP) { return <svg {...base} strokeWidth={2.2} {...p}><path d="M12 5v14M5 12h14" /></svg>; }
function CoinIcon(p: IP) { return <svg {...base} {...p}><circle cx="12" cy="12" r="9" /><path d="M8 12h8M12 8v8" /></svg>; }
function CalendarIcon(p: IP) { return <svg {...base} {...p}><rect x="3" y="4" width="18" height="18" rx="2" /><path d="M16 2v4M8 2v4M3 10h18" /></svg>; }
function ClockIcon(p: IP) { return <svg {...base} {...p}><circle cx="12" cy="12" r="10" /><path d="M12 6v6l4 2" /></svg>; }
function LockIcon(p: IP) { return <svg {...base} {...p}><rect x="4" y="11" width="16" height="10" rx="2" /><path d="M8 11V7a4 4 0 0 1 8 0v4" /></svg>; }
function MailIcon(p: IP) { return <svg {...base} {...p}><rect x="3" y="5" width="18" height="14" rx="2" /><path d="m3 7 9 6 9-6" /></svg>; }
function TrashIcon(p: IP) { return <svg {...base} {...p}><path d="M3 6h18M8 6V4a2 2 0 0 1 2-2h4a2 2 0 0 1 2 2v2M19 6l-1 14a2 2 0 0 1-2 2H8a2 2 0 0 1-2-2L5 6" /></svg>; }
function TicketIcon(p: IP) { return <svg {...base} {...p}><path d="M3 9a2 2 0 0 1 2-2h14a2 2 0 0 1 2 2v2a2 2 0 0 0 0 4v2a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-2a2 2 0 0 0 0-4V9Z" /><path d="M13 7v2M13 13v2M13 17v2" /></svg>; }
function ArrowUpIcon(p: IP) { return <svg {...base} {...p}><path d="m18 15-6-6-6 6" /></svg>; }
function ArrowDnIcon(p: IP) { return <svg {...base} {...p}><path d="m6 9 6 6 6-6" /></svg>; }
function ShieldIcon(p: IP) { return <svg {...base} {...p}><path d="M12 2 4 5v6c0 5 3.5 9 8 11 4.5-2 8-6 8-11V5l-8-3Z" /></svg>; }
function AlertIcon(p: IP) { return <svg {...base} {...p}><path d="M10.3 3.86 1.82 18a2 2 0 0 0 1.71 3h16.94a2 2 0 0 0 1.71-3L13.7 3.86a2 2 0 0 0-3.4 0Z" /><path d="M12 9v4M12 17h.01" /></svg>; }
function GoogleIcon(p: IP) {
  return (
    <svg viewBox="0 0 24 24" {...p}>
      <path fill="#4285F4" d="M23 12.27c0-.82-.07-1.6-.21-2.36H12v4.46h6.18c-.27 1.43-1.08 2.65-2.3 3.46v2.87h3.71C21.74 18.7 23 15.76 23 12.27Z" />
      <path fill="#34A853" d="M12 23c3.11 0 5.71-1.03 7.6-2.79l-3.71-2.87c-1.03.69-2.34 1.1-3.89 1.1-2.99 0-5.52-2.02-6.43-4.74H1.74v2.97A11 11 0 0 0 12 23Z" />
      <path fill="#FBBC05" d="M5.57 13.7a6.6 6.6 0 0 1 0-4.2V6.53H1.74a11 11 0 0 0 0 9.94l3.83-2.77Z" />
      <path fill="#EA4335" d="M12 5.37c1.69 0 3.21.58 4.41 1.72l3.29-3.29C17.7 2 15.1 1 12 1 7.7 1 3.99 3.47 1.74 6.53l3.83 2.97C6.48 7.39 9.01 5.37 12 5.37Z" />
    </svg>
  );
}

/* ── Data types ─────────────────────────────────────────────────────── */
interface SettingsData {
  name: string;
  email: string;
  initials: string;
  dnaTags: string[];
  balance: number;
  totalSpent: number;
  firstClaimed: string | null;
  createdAt: string | null;
  lastSignIn: string | null;
  provider: string; // "google" | "email" | …
  telegramLinked: boolean;
  loading: boolean;
  hasCompletedForm: boolean;
}

function deriveInitials(name: string): string {
  return (
    name.split(/\s+/).filter(Boolean).slice(0, 2).map((w) => w[0].toUpperCase()).join("") || "?"
  );
}

function fmtDate(iso: string | null | undefined): string | null {
  if (!iso) return null;
  return new Date(iso).toLocaleDateString("en-GB", { day: "2-digit", month: "short", year: "numeric" });
}

function fmtDateTime(iso: string | null | undefined): string | null {
  if (!iso) return null;
  const d = new Date(iso);
  return (
    d.toLocaleDateString("en-GB", { day: "2-digit", month: "short", year: "numeric" }) +
    " · " +
    d.toLocaleTimeString("en-GB", { hour: "2-digit", minute: "2-digit" })
  );
}

function daysAgo(iso: string | null): string {
  if (!iso) return "";
  const diff = Math.floor((Date.now() - new Date(iso).getTime()) / 86_400_000);
  if (diff === 0) return "today";
  if (diff === 1) return "yesterday";
  return `${diff} days ago`;
}

/* ── Shared UI atoms ────────────────────────────────────────────────── */
function SectionHeader({
  eyebrow, title, subtitle, icon: I,
}: {
  eyebrow: string; title: string; subtitle: string; icon: (p: IP) => React.ReactElement;
}) {
  return (
    <div className="flex items-start gap-3 mb-5">
      <div
        className="w-9 h-9 rounded-xl grid place-items-center text-primary flex-shrink-0"
        style={{
          background: "color-mix(in oklab, var(--primary) 12%, transparent)",
          border: "1px solid color-mix(in oklab, var(--primary) 25%, transparent)",
        }}
      >
        <I width={16} height={16} />
      </div>
      <div className="min-w-0">
        <div className="text-[10px] font-mono uppercase tracking-[0.18em] text-muted-foreground mb-1">{eyebrow}</div>
        <div className="text-lg font-bold leading-tight">{title}</div>
        <div className="text-sm text-muted-foreground mt-0.5">{subtitle}</div>
      </div>
    </div>
  );
}

function FieldRow({
  label, action, children, alignTop = false,
}: {
  label: string; action?: React.ReactNode; children: React.ReactNode; alignTop?: boolean;
}) {
  return (
    <div className={`flex ${alignTop ? "items-start" : "items-center"} justify-between gap-4 py-3.5 border-t border-border first:border-t-0`}>
      <div className="min-w-0">
        <div className="text-[10px] font-mono uppercase tracking-[0.18em] text-muted-foreground mb-1">{label}</div>
        <div className="text-[15px] font-medium text-foreground">{children}</div>
      </div>
      {action && <div className="flex-shrink-0">{action}</div>}
    </div>
  );
}

/* ── Editable name ──────────────────────────────────────────────────── */
function EditableName({ value, onSave }: { value: string; onSave: (v: string) => Promise<void> }) {
  const [editing, setEditing] = useState(false);
  const [draft, setDraft] = useState(value);
  const [saving, setSaving] = useState(false);
  const [flash, setFlash] = useState(false);
  const inputRef = useRef<HTMLInputElement>(null);

  useEffect(() => {
    if (editing) { inputRef.current?.focus(); inputRef.current?.select(); }
  }, [editing]);

  const cancel = () => { setDraft(value); setEditing(false); };
  const save = async () => {
    const trimmed = draft.trim();
    if (!trimmed || trimmed === value) { setEditing(false); return; }
    setSaving(true);
    await onSave(trimmed);
    setSaving(false);
    setEditing(false);
    setFlash(true);
    setTimeout(() => setFlash(false), 1800);
  };

  if (!editing) {
    return (
      <button
        type="button" onClick={() => { setDraft(value); setEditing(true); }}
        className="group w-full flex items-start justify-between gap-3 py-3.5 -mx-3 px-3 rounded-xl text-left hover:bg-foreground/[0.04] transition"
      >
        <div className="min-w-0">
          <div className="text-[10px] font-mono uppercase tracking-[0.18em] text-muted-foreground mb-1 flex items-center gap-2">
            Full name
            {flash && (
              <span className="inline-flex items-center gap-1 text-emerald-400 normal-case tracking-normal font-sans font-semibold animate-fade-up">
                <CheckIcon width={11} height={11} />Saved
              </span>
            )}
          </div>
          <div className="text-[15px] font-medium truncate">{value}</div>
        </div>
        <span className="flex items-center gap-1.5 text-[11px] font-semibold text-muted-foreground group-hover:text-primary transition flex-shrink-0 mt-px">
          <PencilIcon width={13} height={13} />Edit
        </span>
      </button>
    );
  }

  return (
    <div
      className="relative pt-3 pb-2.5 -mx-3 px-3 rounded-xl"
      style={{
        background: "color-mix(in oklab, var(--primary) 6%, transparent)",
        border: "1px solid color-mix(in oklab, var(--primary) 25%, transparent)",
      }}
    >
      <label className="absolute -top-2.5 left-4 px-1.5 bg-background text-[10px] font-mono uppercase tracking-[0.18em] text-primary">Full name</label>
      <div className="flex items-center gap-2">
        <input
          ref={inputRef} type="text" value={draft}
          onChange={(e) => setDraft(e.target.value)}
          onKeyDown={(e) => { if (e.key === "Enter") save(); if (e.key === "Escape") cancel(); }}
          className="flex-1 h-10 px-3 rounded-lg bg-background border border-border text-foreground text-[15px] font-medium focus:outline-none focus:border-primary"
          disabled={saving}
        />
        <button
          type="button" onClick={cancel} disabled={saving}
          className="h-10 w-10 rounded-lg grid place-items-center text-muted-foreground hover:text-foreground hover:bg-foreground/5 transition disabled:opacity-50"
        >
          <XIcon width={16} height={16} />
        </button>
        <button
          type="button" onClick={save} disabled={saving || !draft.trim()}
          className="h-10 w-10 sm:w-auto sm:px-3.5 rounded-lg text-white font-semibold text-sm inline-flex items-center justify-center gap-1.5 transition disabled:opacity-60 disabled:cursor-not-allowed"
          style={{ background: "linear-gradient(135deg, var(--primary), #9333ea)", boxShadow: "0 8px 20px -8px color-mix(in oklab, var(--primary) 60%, transparent)" }}
          aria-label="Save"
        >
          {saving ? (
            <>
              <span className="w-3 h-3 rounded-full border-2 border-white/40 border-t-white animate-spin" />
              <span className="hidden sm:inline">Saving</span>
            </>
          ) : (
            <>
              <CheckIcon width={14} height={14} />
              <span className="hidden sm:inline">Save</span>
            </>
          )}
        </button>
      </div>

    </div>
  );
}

/* ── Top up modal ───────────────────────────────────────────────────── */
function TopUpModal({ onClose }: { onClose: () => void }) {
  // Close on Escape
  useEffect(() => {
    const onKey = (e: KeyboardEvent) => { if (e.key === "Escape") onClose(); };
    document.addEventListener("keydown", onKey);
    return () => document.removeEventListener("keydown", onKey);
  }, [onClose]);

  return (
    <div
      className="fixed inset-0 z-50 grid place-items-center p-4 animate-fade-up"
      style={{ background: "color-mix(in oklab, var(--background) 70%, transparent)", backdropFilter: "blur(8px)" }}
      onClick={onClose}
      role="dialog"
      aria-modal="true"
    >
      <div
        className="aletheia-card w-full max-w-md p-7 relative"
        onClick={(e) => e.stopPropagation()}
      >
        {/* Close button */}
        <button
          type="button"
          onClick={onClose}
          className="absolute top-4 right-4 w-9 h-9 rounded-full grid place-items-center text-muted-foreground hover:text-foreground hover:bg-foreground/5 transition"
          aria-label="Close"
        >
          <XIcon width={16} height={16} />
        </button>

        {/* Header */}
        <div className="flex items-start gap-3 mb-4">
          <div
            className="w-11 h-11 rounded-xl grid place-items-center flex-shrink-0"
            style={{
              background: "linear-gradient(135deg, var(--primary), #9333ea)",
              boxShadow: "0 14px 30px -10px color-mix(in oklab, var(--primary) 70%, transparent)",
            }}
          >
            <CoinIcon width={20} height={20} className="text-white" />
          </div>
          <div className="min-w-0 mt-1">
            <div className="text-[10px] font-mono uppercase tracking-[0.18em] text-muted-foreground mb-1">Early access</div>
            <h2 className="text-xl font-black tracking-tight leading-tight">Need more credits?</h2>
          </div>
        </div>

        {/* Body */}
        <div className="space-y-3 text-sm text-muted-foreground leading-relaxed">
          <p>
            Aletheia is in <span className="text-foreground font-semibold">early access</span> — automated billing isn&rsquo;t wired up yet, so paid top-ups aren&rsquo;t available through the app.
          </p>
          <p>
            For now, extra credits go out as <span className="text-foreground font-semibold">promo codes</span>. Get in touch and we&rsquo;ll send you one tailored to your use case.
          </p>
        </div>

        {/* Contact CTA */}
        <a
          href="https://www.linkedin.com/in/vasile-cristian-dumitrascu/"
          target="_blank"
          rel="noopener noreferrer"
          className="mt-6 w-full h-11 rounded-xl text-white font-semibold inline-flex items-center justify-center gap-2 transition hover:-translate-y-px"
          style={{
            background: "linear-gradient(135deg, var(--primary), #9333ea)",
            boxShadow: "0 14px 30px -10px color-mix(in oklab, var(--primary) 70%, transparent)",
          }}
        >
          Contact the founder
          <ChevronRightIcon width={14} height={14} />
        </a>

        <div className="mt-3 text-center">
          <span className="text-[11px] font-mono uppercase tracking-wider text-muted-foreground">
            Already have a code? Use the form below.
          </span>
        </div>
      </div>
    </div>
  );
}

/* ── Promo code ─────────────────────────────────────────────────────── */
function PromoCode({ onSuccess }: { onSuccess: (added: number) => void }) {
  const [open, setOpen] = useState(false);
  const [code, setCode] = useState("");
  const [state, setState] = useState<"idle" | "checking" | "success" | "error">("idle");
  const [message, setMessage] = useState("");
  const inputRef = useRef<HTMLInputElement>(null);

  useEffect(() => { if (open) inputRef.current?.focus(); }, [open]);

  const apply = async () => {
    const c = code.trim().toUpperCase();
    if (!c) return;
    setState("checking");
    setMessage("");
    try {
      const res = await fetch("/api/credits/redeem-promo", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ code: c }),
      });
      const json = await res.json();
      if (res.ok && json.success) {
        setState("success");
        setMessage(json.message);
        onSuccess(json.creditsAdded ?? 0);
        setTimeout(() => { setCode(""); setState("idle"); setOpen(false); setMessage(""); }, 2200);
      } else {
        setState("error");
        setMessage(json.error ?? "Failed to apply code.");
      }
    } catch {
      setState("error");
      setMessage("Network error. Please try again.");
    }
  };

  if (!open) {
    return (
      <button
        type="button" onClick={() => setOpen(true)}
        className="mt-3 w-full h-9 rounded-lg text-[12px] font-medium inline-flex items-center justify-center gap-2 transition text-muted-foreground hover:text-foreground hover:bg-foreground/[0.04]"
        style={{ background: "transparent" }}
      >
        <TicketIcon width={13} height={13} />
        Have a promo code?
      </button>
    );
  }

  return (
    <div
      className="mt-2 rounded-xl p-3"
      style={{
        background: "color-mix(in oklab, var(--primary) 5%, transparent)",
        border: "1px solid color-mix(in oklab, var(--primary) 22%, transparent)",
      }}
    >
      <label className="text-[10px] font-mono uppercase tracking-[0.18em] text-muted-foreground mb-1.5 block">Promo code</label>
      <div className="flex items-center gap-2">
        <input
          ref={inputRef} type="text" value={code}
          onChange={(e) => { setCode(e.target.value.toUpperCase()); if (state !== "idle") { setState("idle"); setMessage(""); } }}
          onKeyDown={(e) => { if (e.key === "Enter") apply(); if (e.key === "Escape") setOpen(false); }}
          placeholder="ENTER CODE"
          disabled={state === "checking" || state === "success"}
          className="flex-1 h-10 px-3 rounded-lg bg-background border text-foreground text-[14px] font-mono tracking-wider focus:outline-none focus:border-primary disabled:opacity-60"
          style={{
            borderColor:
              state === "error" ? "rgba(239,68,68,.5)" :
                state === "success" ? "rgba(16,185,129,.5)" :
                  "var(--border)",
          }}
        />
        <button
          type="button" onClick={() => { setOpen(false); setCode(""); setState("idle"); setMessage(""); }}
          className="h-10 w-10 rounded-lg grid place-items-center text-muted-foreground hover:text-foreground hover:bg-foreground/5 transition"
        >
          <XIcon width={16} height={16} />
        </button>
        <button
          type="button" onClick={apply}
          disabled={!code.trim() || state === "checking" || state === "success"}
          className="h-10 px-4 rounded-lg text-white font-semibold text-sm inline-flex items-center gap-1.5 transition disabled:opacity-60 disabled:cursor-not-allowed"
          style={{ background: "linear-gradient(135deg, var(--primary), #9333ea)", boxShadow: "0 8px 20px -8px color-mix(in oklab, var(--primary) 60%, transparent)" }}
        >
          {state === "checking" && <><span className="w-3 h-3 rounded-full border-2 border-white/40 border-t-white animate-spin" />Checking</>}
          {state === "success" && <><CheckIcon width={14} height={14} />Applied</>}
          {(state === "idle" || state === "error") && <>Apply</>}
        </button>
      </div>
      {message && (
        <div className={`mt-2 text-[12px] flex items-center gap-1.5 ${state === "success" ? "text-emerald-400" : "text-rose-400"}`}>
          {state === "success" ? <CheckIcon width={12} height={12} /> : <AlertIcon width={12} height={12} />}
          {message}
        </div>
      )}
      {state === "idle" && !message && (
        <div className="mt-2 text-[11px] text-muted-foreground">
          Codes are case-insensitive. Contact the founder for one tailored to you.
        </div>
      )}
    </div>
  );
}

/* ── Profile section ────────────────────────────────────────────────── */
function ProfileSection({
  data, onNameSave,
}: {
  data: SettingsData;
  onNameSave: (n: string) => Promise<void>;
}) {
  const [showInfo, setShowInfo] = useState(false);

  return (
    <section className="aletheia-card p-7">
      <SectionHeader
        icon={SparklesIcon}
        eyebrow="01 · Profile"
        title="Who you are"
        subtitle="The name we use across recommendations and itineraries."
      />
      <div className="grid grid-cols-1 sm:grid-cols-[auto_1fr] gap-7 items-start">
        {/* Avatar */}
        <div className="flex flex-col items-center gap-2">
          <div
            className="w-24 h-24 rounded-full grid place-items-center text-white font-black text-2xl"
            style={{
              background: "linear-gradient(135deg, #f59e0b, #ec4899)",
              boxShadow: "0 20px 40px -15px color-mix(in oklab, var(--primary) 50%, transparent), 0 0 0 4px var(--background), 0 0 0 5px color-mix(in oklab, var(--primary) 40%, transparent)",
            }}
          >
            {data.initials}
          </div>
          <div className="text-[10px] font-mono uppercase tracking-[0.18em] text-muted-foreground">Initials</div>
        </div>

        {/* Name + email */}
        <div>
          <EditableName value={data.name} onSave={onNameSave} />
          <div className="py-3.5 border-t border-border">
            <div className="flex items-center justify-between gap-4 mb-1">
              <div className="text-[10px] font-mono uppercase tracking-[0.18em] text-muted-foreground">Email address</div>
              <span
                className="inline-flex items-center gap-1 px-1.5 py-0.5 rounded-full text-[9px] font-bold uppercase tracking-wider flex-shrink-0"
                style={{ background: "color-mix(in oklab, #10b981 14%, transparent)", color: "#34d399" }}
              >
                <span className="w-1.5 h-1.5 rounded-full bg-emerald-400 flex-shrink-0" />Verified
              </span>
            </div>
            <div className="text-[15px] font-medium text-foreground">
              <span className="font-mono text-[14px]">{data.email}</span>
            </div>
          </div>
        </div>
      </div>

      {/* Traveler DNA */}
      <div className="mt-7 pt-6 border-t border-border">
        <div className="flex items-center justify-between mb-4">
          <div className="text-[10px] font-mono uppercase tracking-[0.18em] text-muted-foreground">Traveler DNA</div>
          {(data.hasCompletedForm || data.dnaTags.length > 0) && (
            <div className="flex items-center gap-1.5">
              <button
                type="button"
                disabled={data.balance === 0}
                onClick={async () => {
                  if (data.balance === 0) return;
                  try {
                    const res = await fetch("/api/account/onboarding-link", { method: "POST" });
                    const d = await res.json();
                    if (d?.url) {
                      window.open(d.url, "_blank");
                    }
                  } catch (err) {
                    console.error("Failed to load onboarding link:", err);
                  }
                }}
                className={`text-xs font-semibold inline-flex items-center gap-1 ${data.balance === 0
                    ? "text-muted-foreground/50 cursor-not-allowed no-underline"
                    : "text-primary hover:underline"
                  }`}
              >
                Re-take quiz <ChevronRightIcon width={12} height={12} />
              </button>
              {data.balance === 0 && (
                <button
                  type="button"
                  onClick={() => setShowInfo((v) => !v)}
                  className="text-muted-foreground/60 hover:text-foreground inline-flex items-center focus:outline-none"
                  title="Why is this disabled?"
                >
                  <svg viewBox="0 0 24 24" width={13} height={13} fill="none" stroke="currentColor" strokeWidth={2.5} strokeLinecap="round" strokeLinejoin="round">
                    <circle cx="12" cy="12" r="10" />
                    <path d="M12 16v-4" />
                    <path d="M12 8h.01" />
                  </svg>
                </button>
              )}
            </div>
          )}
        </div>
        {(data.hasCompletedForm || data.dnaTags.length > 0) ? (
          data.dnaTags.length > 0 ? (
            <div className="flex flex-wrap gap-2">
              {data.dnaTags.map((t) => (
                <span
                  key={t}
                  className="inline-flex items-center gap-1.5 px-3 py-1.5 rounded-full text-[12px] font-semibold"
                  style={{
                    background: "color-mix(in oklab, var(--primary) 14%, transparent)",
                    border: "1px solid color-mix(in oklab, var(--primary) 35%, transparent)",
                  }}
                >
                  <span className="w-1.5 h-1.5 rounded-full bg-primary" />
                  {t}
                </span>
              ))}
            </div>
          ) : (
            <p className="text-sm text-muted-foreground italic">
              Form submitted! Syncing your Traveler DNA...
            </p>
          )
        ) : (
          <p className="text-sm text-muted-foreground italic">
            No DNA tags yet —{" "}
            <button
              type="button"
              disabled={data.balance === 0}
              onClick={async () => {
                if (data.balance === 0) return;
                try {
                  const res = await fetch("/api/account/onboarding-link", { method: "POST" });
                  const d = await res.json();
                  if (d?.url) {
                    window.open(d.url, "_blank");
                  }
                } catch (err) {
                  console.error("Failed to load onboarding link:", err);
                }
              }}
              className={`font-semibold not-italic ${data.balance === 0
                  ? "text-muted-foreground/50 cursor-not-allowed no-underline"
                  : "text-primary hover:underline"
                }`}
            >
              complete the onboarding quiz
            </button>
            {data.balance === 0 && (
              <button
                type="button"
                onClick={() => setShowInfo((v) => !v)}
                className="ml-1 text-muted-foreground/60 hover:text-foreground inline-flex items-center focus:outline-none"
                title="Why is this disabled?"
              >
                <svg viewBox="0 0 24 24" width={13} height={13} fill="none" stroke="currentColor" strokeWidth={2.5} strokeLinecap="round" strokeLinejoin="round" className="inline">
                  <circle cx="12" cy="12" r="10" />
                  <path d="M12 16v-4" />
                  <path d="M12 8h.01" />
                </svg>
              </button>
            )}
            .
          </p>
        )}
        {data.balance === 0 && showInfo && (
          <p className="mt-3 text-xs text-amber-500/90 leading-normal max-w-md animate-fade-up">
            Taking the quiz requires active credits to map your Traveler DNA. Please top up your balance to proceed.
          </p>
        )}
      </div>
    </section>
  );
}

/* ── Credits section ────────────────────────────────────────────────── */
function CreditsSection({
  data, onPromoSuccess,
}: {
  data: SettingsData;
  onPromoSuccess: (added: number) => void;
}) {
  const { balance, totalSpent, firstClaimed } = data;
  const [topUpOpen, setTopUpOpen] = useState(false);

  return (
    <section className="aletheia-card p-7">
      <SectionHeader
        icon={CoinIcon}
        eyebrow="02 · Credits"
        title="Plan & balance"
        subtitle="Credits power AI-generated days, replans, and trip suggestions."
      />
      <div className="grid grid-cols-1 md:grid-cols-[1.2fr_1fr] gap-5">
        {/* Balance widget */}
        <div
          className="relative rounded-2xl p-5 overflow-hidden"
          style={{
            background: "linear-gradient(135deg, color-mix(in oklab, var(--primary) 22%, var(--muted)) 0%, color-mix(in oklab, #9333ea 18%, var(--muted)) 100%)",
            border: "1px solid color-mix(in oklab, var(--primary) 30%, transparent)",
          }}
        >
          <div
            className="absolute -top-10 -right-10 w-40 h-40 rounded-full blur-3xl pointer-events-none"
            style={{ background: "radial-gradient(circle, color-mix(in oklab, #9333ea 50%, transparent), transparent 70%)" }}
          />
          <div className="relative">
            <div className="text-[10px] font-mono uppercase tracking-[0.18em] text-muted-foreground mb-1">Available balance</div>
            <div>
              <span
                className="text-6xl font-black tracking-tight leading-none tabular-nums"
                style={{ color: balance === 0 ? "#fb7185" : "var(--foreground)" }}
              >
                {balance}
              </span>
              <div className="text-[11px] text-muted-foreground font-mono uppercase tracking-wider mt-1">
                credit{balance === 1 ? "" : "s"} remaining
              </div>
            </div>

            {/* Remaining / Used strip */}
            <div className="mt-5 grid grid-cols-2 gap-3">
              <div
                className="rounded-xl p-3 flex flex-col items-center text-center"
                style={{ background: "color-mix(in oklab, var(--background) 35%, transparent)", border: "1px solid color-mix(in oklab, var(--foreground) 8%, transparent)" }}
              >
                <div className="flex items-center gap-1.5 text-[10px] font-mono uppercase tracking-wider text-muted-foreground">
                  <ArrowDnIcon width={11} height={11} className="text-emerald-400" />Remaining
                </div>
                <div className="mt-1 text-2xl font-black tabular-nums">{balance}</div>
              </div>
              <div
                className="rounded-xl p-3 flex flex-col items-center text-center"
                style={{ background: "color-mix(in oklab, var(--background) 35%, transparent)", border: "1px solid color-mix(in oklab, var(--foreground) 8%, transparent)" }}
              >
                <div className="flex items-center gap-1.5 text-[10px] font-mono uppercase tracking-wider text-muted-foreground">
                  <ArrowUpIcon width={11} height={11} className="text-primary" />Used so far
                </div>
                <div className="mt-1 text-2xl font-black tabular-nums">{totalSpent}</div>
              </div>
            </div>

            <button
              type="button"
              onClick={() => setTopUpOpen(true)}
              className="mt-5 w-full h-11 rounded-xl text-white font-semibold inline-flex items-center justify-center gap-2 transition hover:-translate-y-px"
              style={{ background: "linear-gradient(135deg, var(--primary), #9333ea)", boxShadow: "0 14px 30px -10px color-mix(in oklab, var(--primary) 70%, transparent)" }}
            >
              <PlusIcon width={16} height={16} />
              Top up credits
            </button>

            <PromoCode onSuccess={onPromoSuccess} />
          </div>
        </div>

        {topUpOpen && <TopUpModal onClose={() => setTopUpOpen(false)} />}

        {/* Meta column */}
        <div className="flex flex-col">
          <FieldRow label="Initial credit claimed">
            <span className="inline-flex items-center gap-2 text-foreground/90">
              <CalendarIcon width={14} height={14} className="text-muted-foreground" />
              {firstClaimed ?? <span className="text-muted-foreground italic">Not yet claimed</span>}
            </span>
          </FieldRow>
          <FieldRow label="Lifetime credits used">
            <span className="font-mono tabular-nums">{totalSpent}</span>
          </FieldRow>
          <FieldRow label="Renewal">
            <span className="text-muted-foreground italic">Pay-as-you-go · no recurring charge</span>
          </FieldRow>
          <div className="mt-auto pt-4">
            <Link
              href="/pricing"
              className="inline-flex items-center justify-center gap-1.5 h-9 px-4 rounded-full text-xs font-semibold transition hover:-translate-y-px"
              style={{
                background: "color-mix(in oklab, var(--primary) 10%, transparent)",
                border: "1px solid color-mix(in oklab, var(--primary) 30%, transparent)",
                color: "var(--primary)",
              }}
            >
              See pricing <ChevronRightIcon width={12} height={12} />
            </Link>
          </div>
        </div>
      </div>
    </section>
  );
}

/* ── Account info ───────────────────────────────────────────────────── */
function AccountInfoSection({ data }: { data: SettingsData }) {
  return (
    <section className="aletheia-card p-7">
      <SectionHeader
        icon={ClockIcon}
        eyebrow="03 · Account"
        title="Account info"
        subtitle="Timestamps from your account record."
      />
      <div>
        <FieldRow label="Account created">
          <span className="inline-flex items-center gap-2">
            <CalendarIcon width={14} height={14} className="text-muted-foreground" />
            {data.createdAt ?? "—"}
            {data.createdAt && (
              <span className="text-[11px] font-mono text-muted-foreground">· {daysAgo(data.createdAt)}</span>
            )}
          </span>
        </FieldRow>
        <FieldRow label="Last sign-in">
          <span className="inline-flex items-center gap-2">
            <span className="relative flex w-2 h-2">
              <span className="absolute inset-0 rounded-full bg-emerald-400 animate-ping opacity-60" />
              <span className="relative w-2 h-2 rounded-full bg-emerald-400" />
            </span>
            {data.lastSignIn ?? "—"}
            <span className="text-[11px] font-mono text-muted-foreground">· this device</span>
          </span>
        </FieldRow>
      </div>
    </section>
  );
}

/* ── Security ───────────────────────────────────────────────────────── */
function SecuritySection({
  data,
  linkingTelegram,
  onLinkTelegram,
  botUsername,
  isPollingTelegram,
  linkToken,
}: {
  data: SettingsData;
  linkingTelegram: boolean;
  onLinkTelegram: () => void;
  botUsername: string;
  isPollingTelegram: boolean;
  linkToken: string;
}) {
  const isGoogle = data.provider === "google";
  const [copied, setCopied] = useState(false);

  const handleCopy = () => {
    navigator.clipboard.writeText(`/start link_${linkToken}`);
    setCopied(true);
    setTimeout(() => setCopied(false), 2000);
  };

  return (
    <section className="aletheia-card p-7">
      <SectionHeader
        icon={ShieldIcon}
        eyebrow="04 · Security"
        title="Sign-in & security"
        subtitle="How you access your account."
      />
      <div>
        <FieldRow label="Email address">
          <span className="font-mono text-[14px]">{data.email}</span>
        </FieldRow>

        <FieldRow
          label="Auth provider"
          action={
            <span
              className="inline-flex items-center gap-2 px-3 py-1.5 rounded-full text-[12px] font-semibold"
              style={{ background: "color-mix(in oklab, var(--foreground) 4%, transparent)", border: "1px solid var(--border)" }}
            >
              {isGoogle ? <GoogleIcon width={14} height={14} /> : <MailIcon width={14} height={14} />}
              {isGoogle ? "Google" : "Email & password"}
            </span>
          }
        >
          {isGoogle ? "Signed in with Google" : "Email & password"}
        </FieldRow>

        <FieldRow
          label="Password"
          action={
            isGoogle ? (
              <button
                type="button"
                disabled
                className="h-9 px-4 rounded-full text-sm font-semibold inline-flex items-center gap-1.5 opacity-50 cursor-not-allowed"
                style={{ background: "color-mix(in oklab, var(--foreground) 4%, transparent)", border: "1px solid var(--border)" }}
              >
                <LockIcon width={13} height={13} />
                Change password
              </button>
            ) : (
              <Link
                href="/forgot-password"
                className="h-9 px-4 rounded-full text-sm font-semibold inline-flex items-center gap-1.5 transition hover:bg-foreground/[0.04]"
                style={{ background: "color-mix(in oklab, var(--foreground) 4%, transparent)", border: "1px solid var(--border)" }}
              >
                <LockIcon width={13} height={13} />
                Change password
              </Link>
            )
          }
        >
          <span className="text-muted-foreground italic">
            {isGoogle
              ? "Managed by Google — use your provider to update"
              : "••••••••••••"}
          </span>
        </FieldRow>

        <FieldRow
          label="Telegram Integration"
          action={
            data.telegramLinked ? (
              <div className="flex items-center gap-3">
                <span
                  className="inline-flex items-center gap-1.5 px-3 py-1.5 rounded-full text-[12px] font-semibold text-emerald-400 bg-emerald-400/10 border border-emerald-400/20"
                >
                  <CheckIcon width={13} height={13} />
                  Linked
                </span>
                <a
                  href={`https://t.me/${botUsername}`}
                  target="_blank"
                  rel="noopener noreferrer"
                  className="inline-flex items-center gap-1 text-xs font-semibold text-primary hover:underline"
                >
                  Open chat
                  <ChevronRightIcon width={12} height={12} />
                </a>
              </div>
            ) : (
              <button
                type="button"
                onClick={onLinkTelegram}
                disabled={linkingTelegram}
                className="h-9 px-4 rounded-full text-sm font-semibold inline-flex items-center gap-1.5 transition hover:-translate-y-px"
                style={{
                  background: "color-mix(in oklab, var(--primary) 10%, transparent)",
                  border: "1px solid color-mix(in oklab, var(--primary) 30%, transparent)",
                  color: "var(--primary)",
                }}
              >
                {linkingTelegram ? (
                  <>
                    <span className="w-3 h-3 rounded-full border-2 border-primary/30 border-t-primary animate-spin" />
                    Connecting…
                  </>
                ) : (
                  "Link Telegram"
                )}
              </button>
            )
          }
        >
          {data.telegramLinked ? (
            <span className="text-foreground">Connected to Telegram bot</span>
          ) : (
            <span className="text-muted-foreground italic">Link your Telegram account</span>
          )}
        </FieldRow>

        {isPollingTelegram && linkToken && (
          <div
            className="mt-4 p-4 rounded-xl text-sm space-y-3 border transition-all animate-fade-up"
            style={{
              background: "color-mix(in oklab, var(--primary) 4%, transparent)",
              borderColor: "color-mix(in oklab, var(--primary) 20%, transparent)",
            }}
          >
            <div className="font-bold flex items-center gap-2 text-primary">
              <span className="w-2 h-2 rounded-full bg-primary animate-pulse" />
              Waiting for Telegram connection...
            </div>
            <p className="text-muted-foreground text-xs leading-relaxed">
              If the Telegram app did not open automatically, you can link manually:
            </p>
            <ol className="list-decimal list-inside space-y-1.5 text-xs text-muted-foreground">
              <li>Open your Telegram app (on phone or web).</li>
              <li>Search for <span className="font-semibold text-foreground">@{botUsername}</span>.</li>
              <li>Send this command to the bot chat:</li>
            </ol>
            <div className="flex items-center gap-2 p-2.5 rounded-lg bg-background border border-border mt-1">
              <code className="text-xs font-mono select-all truncate flex-1 text-foreground">
                /start link_{linkToken}
              </code>
              <button
                type="button"
                onClick={handleCopy}
                className="h-8 px-3 rounded-md text-[11px] font-semibold transition bg-primary text-white hover:bg-primary-hover flex-shrink-0"
              >
                {copied ? "Copied!" : "Copy command"}
              </button>
            </div>
          </div>
        )}
      </div>
    </section>
  );
}

/* ── Misc (theme + language) ────────────────────────────────────────── */
function SunIcon(p: IP) { return <svg {...base} {...p}><circle cx="12" cy="12" r="4" /><path d="M12 2v2M12 20v2M4.9 4.9l1.4 1.4M17.7 17.7l1.4 1.4M2 12h2M20 12h2M4.9 19.1l1.4-1.4M17.7 6.3l1.4-1.4" /></svg>; }
function MoonIcon(p: IP) { return <svg {...base} {...p}><path d="M21 12.8A9 9 0 1 1 11.2 3a7 7 0 0 0 9.8 9.8Z" /></svg>; }
function CogIcon(p: IP) { return <svg {...base} {...p}><circle cx="12" cy="12" r="3" /><path d="M19.4 15a1.65 1.65 0 0 0 .33 1.82l.06.06a2 2 0 0 1-2.83 2.83l-.06-.06a1.65 1.65 0 0 0-1.82-.33 1.65 1.65 0 0 0-1 1.51V21a2 2 0 0 1-4 0v-.09A1.65 1.65 0 0 0 9 19.4a1.65 1.65 0 0 0-1.82.33l-.06.06a2 2 0 0 1-2.83-2.83l.06-.06A1.65 1.65 0 0 0 4.68 15a1.65 1.65 0 0 0-1.51-1H3a2 2 0 0 1 0-4h.09A1.65 1.65 0 0 0 4.6 9a1.65 1.65 0 0 0-.33-1.82l-.06-.06a2 2 0 0 1 2.83-2.83l.06.06A1.65 1.65 0 0 0 9 4.68a1.65 1.65 0 0 0 1-1.51V3a2 2 0 0 1 4 0v.09a1.65 1.65 0 0 0 1 1.51 1.65 1.65 0 0 0 1.82-.33l.06-.06a2 2 0 0 1 2.83 2.83l-.06.06A1.65 1.65 0 0 0 19.4 9a1.65 1.65 0 0 0 1.51 1H21a2 2 0 0 1 0 4h-.09a1.65 1.65 0 0 0-1.51 1Z" /></svg>; }

// Alphabetical. English is enabled; others are placeholders.
const LANGUAGES = [
  { code: "nl", name: "Dutch", flag: "🇳🇱", enabled: false },
  { code: "en", name: "English", flag: "🇬🇧", enabled: true },
  { code: "fr", name: "French", flag: "🇫🇷", enabled: false },
  { code: "it", name: "Italian", flag: "🇮🇹", enabled: false },
  { code: "ro", name: "Romanian", flag: "🇷🇴", enabled: false },
];

function useThemeMode() {
  const [isDark, setIsDark] = useState(
    () => typeof document !== "undefined" && document.documentElement.classList.contains("dark")
  );
  useEffect(() => {
    const el = document.documentElement;
    const obs = new MutationObserver(() => setIsDark(el.classList.contains("dark")));
    obs.observe(el, { attributes: true, attributeFilter: ["class"] });
    return () => obs.disconnect();
  }, []);
  const toggle = (dark: boolean) => {
    const el = document.documentElement;
    if (dark) { el.classList.add("dark"); localStorage.setItem("theme", "dark"); }
    else { el.classList.remove("dark"); localStorage.setItem("theme", "light"); }
  };
  return { isDark, toggle };
}

function MiscSection() {
  const { isDark, toggle } = useThemeMode();

  return (
    <section className="aletheia-card p-7">
      <SectionHeader
        icon={CogIcon}
        eyebrow="05 · Preferences"
        title="App preferences"
        subtitle="Theme and language settings."
      />
      <div>
        {/* Theme */}
        <FieldRow
          label="Theme"
          action={
            <div
              className="flex rounded-lg border border-border p-0.5 gap-0.5"
              style={{ background: "color-mix(in oklab, var(--foreground) 4%, transparent)" }}
            >
              <button
                type="button" onClick={() => toggle(false)}
                className={`flex items-center gap-1.5 px-3 py-1.5 rounded-md text-xs font-semibold transition-all ${!isDark ? "bg-primary/15 text-primary" : "text-muted-foreground hover:text-foreground"
                  }`}
              >
                <SunIcon width={13} height={13} />Day
              </button>
              <button
                type="button" onClick={() => toggle(true)}
                className={`flex items-center gap-1.5 px-3 py-1.5 rounded-md text-xs font-semibold transition-all ${isDark ? "bg-primary/15 text-primary" : "text-muted-foreground hover:text-foreground"
                  }`}
              >
                <MoonIcon width={13} height={13} />Night
              </button>
            </div>
          }
        >
          <span>{isDark ? "Night mode" : "Day mode"}</span>
        </FieldRow>

        {/* Language */}
        <div className="py-3.5 border-t border-border">
          <div className="flex items-center justify-between gap-4 mb-3">
            <div>
              <div className="text-[10px] font-mono uppercase tracking-[0.18em] text-muted-foreground mb-1">App language</div>
              <div className="text-[15px] font-medium text-foreground">English</div>
            </div>
            <span className="text-[10px] font-mono uppercase tracking-wider text-muted-foreground">
              More coming soon
            </span>
          </div>
          <div className="flex flex-wrap gap-2">
            {LANGUAGES.map((lang) => {
              const isSelected = lang.enabled;
              return (
                <button
                  key={lang.code}
                  type="button"
                  disabled={!lang.enabled}
                  className={`inline-flex items-center gap-1.5 px-3 py-1.5 rounded-full text-[12px] font-semibold transition ${isSelected
                    ? ""
                    : "opacity-50 cursor-not-allowed"
                    }`}
                  title={lang.enabled ? "" : "Coming soon"}
                  style={
                    isSelected
                      ? {
                        background: "color-mix(in oklab, var(--primary) 14%, transparent)",
                        border: "1px solid color-mix(in oklab, var(--primary) 35%, transparent)",
                        color: "var(--foreground)",
                      }
                      : {
                        background: "color-mix(in oklab, var(--foreground) 4%, transparent)",
                        border: "1px solid var(--border)",
                        color: "var(--muted-foreground)",
                      }
                  }
                >
                  <span>{lang.flag}</span>
                  {lang.name}
                  {isSelected && (
                    <span
                      className="ml-1 inline-flex items-center gap-0.5 px-1.5 py-0.5 rounded-full text-[9px] font-bold uppercase tracking-wider"
                      style={{ background: "color-mix(in oklab, var(--primary) 25%, transparent)", color: "var(--primary)" }}
                    >
                      Selected
                    </span>
                  )}
                </button>
              );
            })}
          </div>
          <p className="text-[11px] text-muted-foreground italic mt-3">
            Other languages are on the way. English for now.
          </p>
        </div>
      </div>
    </section>
  );
}

/* ── Danger zone ────────────────────────────────────────────────────── */
function DangerSection() {
  const [confirming, setConfirming] = useState(false);
  const [confirmText, setConfirmText] = useState("");
  const [deleting, setDeleting] = useState(false);
  const [error, setError] = useState("");
  const canDelete = confirmText.trim().toLowerCase() === "delete my account";

  const handleDelete = async () => {
    if (!canDelete) return;
    setDeleting(true);
    setError("");
    try {
      const res = await fetch("/api/account/delete", { method: "POST" });
      if (res.ok) {
        window.location.href = "/login";
      } else {
        const json = await res.json().catch(() => ({}));
        setError(json.error ?? "Failed to delete account.");
        setDeleting(false);
      }
    } catch {
      setError("Network error. Please try again.");
      setDeleting(false);
    }
  };

  return (
    <section
      className="rounded-[1.75rem] p-7 relative overflow-hidden"
      style={{
        background: "color-mix(in oklab, #ef4444 6%, var(--background) 70%)",
        border: "1px solid color-mix(in oklab, #ef4444 35%, transparent)",
        backdropFilter: "blur(20px)",
      }}
    >
      <div
        className="absolute -top-16 -right-16 w-48 h-48 rounded-full blur-3xl pointer-events-none"
        style={{ background: "radial-gradient(circle, rgba(239,68,68,.18), transparent 70%)" }}
      />
      <div className="relative">
        <div className="flex items-start gap-3 mb-5">
          <div
            className="w-9 h-9 rounded-xl grid place-items-center flex-shrink-0"
            style={{ background: "rgba(239,68,68,.14)", border: "1px solid rgba(239,68,68,.3)", color: "#fb7185" }}
          >
            <AlertIcon width={16} height={16} />
          </div>
          <div>
            <div className="text-[10px] font-mono uppercase tracking-[0.18em] mb-1" style={{ color: "#fb7185" }}>06 · Danger zone</div>
            <div className="text-lg font-bold leading-tight">Delete account</div>
            <div className="text-sm text-muted-foreground mt-0.5">
              Permanently erase your account, journeys, Traveler DNA, and remaining credits. This cannot be undone.
            </div>
          </div>
        </div>

        {!confirming ? (
          <div className="flex items-center justify-between gap-4 pt-4 border-t" style={{ borderColor: "rgba(239,68,68,.2)" }}>
            <div className="text-[12px] text-muted-foreground">
              We&apos;ll keep nothing — no shadow copies, no analytics tied to you.
            </div>
            <button
              type="button" onClick={() => setConfirming(true)}
              className="h-10 px-4 rounded-full font-semibold text-sm inline-flex items-center gap-2 whitespace-nowrap flex-shrink-0 transition hover:-translate-y-px"
              style={{ background: "rgba(239,68,68,.12)", border: "1px solid rgba(239,68,68,.4)", color: "#fb7185" }}
            >
              <TrashIcon width={16} height={16} />Delete account
            </button>
          </div>
        ) : (
          <div className="pt-4 border-t" style={{ borderColor: "rgba(239,68,68,.2)" }}>
            <label className="text-[11px] font-mono uppercase tracking-wider mb-2 block" style={{ color: "#fb7185" }}>
              Type &quot;<span className="text-foreground">delete my account</span>&quot; to confirm
            </label>
            <div className="flex flex-col sm:flex-row gap-2">
              <input
                type="text" value={confirmText}
                onChange={(e) => setConfirmText(e.target.value)}
                placeholder="delete my account"
                className="w-full sm:flex-1 h-11 px-3 rounded-lg bg-background text-foreground text-[14px] font-mono focus:outline-none focus:border-rose-400"
                style={{ border: "1px solid rgba(239,68,68,.3)" }}
              />
              <button
                type="button"
                onClick={() => { setConfirming(false); setConfirmText(""); setError(""); }}
                className="w-full sm:w-auto h-11 px-4 rounded-lg text-sm font-semibold text-muted-foreground hover:text-foreground hover:bg-foreground/5 transition"
              >
                Cancel
              </button>
              <button
                type="button" disabled={!canDelete || deleting} onClick={handleDelete}
                className="w-full sm:w-auto h-11 px-4 rounded-lg font-semibold text-sm inline-flex items-center justify-center gap-2 transition disabled:opacity-40 disabled:cursor-not-allowed text-white"
                style={{ background: canDelete ? "linear-gradient(135deg, #ef4444, #be123c)" : "rgba(239,68,68,.3)" }}
              >
                {deleting
                  ? <><span className="w-3 h-3 rounded-full border-2 border-white/40 border-t-white animate-spin" />Deleting…</>
                  : <><TrashIcon width={16} height={16} />Permanently delete</>}
              </button>
            </div>
            {error && <p className="mt-2 text-[12px] text-rose-400">{error}</p>}
          </div>
        )}
      </div>
    </section>
  );
}

/* ── Top nav ────────────────────────────────────────────────────────── */
function SettingsNav() {
  return (
    <nav
      className="h-14 px-4 flex items-center justify-between border-b border-border flex-shrink-0 aletheia-card"
      style={{ borderRadius: 0 }}
    >
      <div className="flex items-center gap-3">
        <Link
          href="/dashboard"
          className="w-9 h-9 rounded-full grid place-items-center text-muted-foreground hover:text-foreground hover:bg-foreground/5 transition"
          title="Back to dashboard"
        >
          <BackIcon width={18} height={18} />
        </Link>
        {/* Logo + wordmark — desktop only */}
        <div className="hidden sm:flex items-center gap-3">
          <div className="w-px h-5 bg-border" />
          <Link href="/dashboard" className="flex items-center gap-2 group">
            <div
              className="w-9 h-9 rounded-xl flex items-center justify-center transition-transform group-hover:scale-110"
              style={{ background: "linear-gradient(135deg, var(--primary), #9333ea)", boxShadow: "0 8px 20px -8px color-mix(in oklab, var(--primary) 60%, transparent)" }}
            >
              <SparklesIcon width={20} height={20} className="text-white" />
            </div>
            <span className="text-lg font-black tracking-tighter">Aletheia</span>
          </Link>
        </div>
      </div>

      <div className="flex items-center gap-2 text-[11px] font-mono uppercase tracking-[0.18em] text-muted-foreground">
        <span>Settings</span>
        <ChevronRightIcon width={12} height={12} />
        <span className="text-foreground">Account</span>
      </div>

      {/* Empty placeholder to keep breadcrumb centered */}
      <div className="w-9 h-9" aria-hidden="true" />
    </nav>
  );
}

/* ── Root component ─────────────────────────────────────────────────── */
export function AccountSettings({ botUsername }: { botUsername: string }) {
  const [data, setData] = useState<SettingsData>({
    name: "", email: "", initials: "…", dnaTags: [],
    balance: 0, totalSpent: 0, firstClaimed: null,
    createdAt: null, lastSignIn: null, provider: "",
    telegramLinked: false, loading: true, hasCompletedForm: false,
  });

  const [linkingTelegram, setLinkingTelegram] = useState(false);
  const [isPollingTelegram, setIsPollingTelegram] = useState(false);
  const [linkToken, setLinkToken] = useState("");

  // Load all settings data client-side
  useEffect(() => {
    let cancelled = false;
    (async () => {
      try {
        const supabase = createClient();

        const { data: { user } } = await supabase.auth.getUser();
        if (!user || cancelled) return;

        const email = user.email ?? "";
        const provider = (user.app_metadata?.provider as string) ?? "email";
        const lastSignIn = fmtDateTime(user.last_sign_in_at);

        const [usersResult, creditsResult] = await Promise.all([
          supabase.from("users").select("name, telegram_id, created_at, user_profiles(profile_data, form_response, summary)").maybeSingle(),
          supabase.from("credits").select("balance, total_spent, welcome_credits_claimed_at").maybeSingle(),
        ]);

        if (cancelled) return;

        const rawProfile = usersResult.data?.user_profiles;
        const profileRow = (Array.isArray(rawProfile) ? rawProfile[0] : rawProfile) as {
          profile_data: { tags?: string[] } | null;
          form_response: any;
          summary: string | null;
        } | null;
        const name = usersResult.data?.name || email.split("@")[0] || "Traveler";
        const dnaTags = profileRow?.profile_data?.tags ?? [];
        const cred = creditsResult.data;

        const formResponse = profileRow?.form_response || null;
        const hasCompletedForm =
          formResponse != null &&
          typeof formResponse === "object" &&
          Object.keys(formResponse).length > 0;

        setData({
          name,
          email,
          initials: deriveInitials(name),
          dnaTags,
          balance: cred?.balance ?? 0,
          totalSpent: cred?.total_spent ?? 0,
          firstClaimed: fmtDate(cred?.welcome_credits_claimed_at),
          createdAt: fmtDate(usersResult.data?.created_at),
          lastSignIn,
          provider,
          telegramLinked: !!usersResult.data?.telegram_id,
          loading: false,
          hasCompletedForm,
        });
      } catch (err) {
        console.error("[AccountSettings] unhandled exception during load:", err);
        if (!cancelled) {
          setData((d) => ({ ...d, loading: false }));
        }
      }
    })();
    return () => { cancelled = true; };
  }, []);

  // Ephemeral polling to detect successful Telegram linking (starts only when redirected)
  useEffect(() => {
    if (!isPollingTelegram) return;

    let cancelled = false;
    const checkLink = async () => {
      const supabase = createClient();
      const { data: { user } } = await supabase.auth.getUser();
      if (!user || cancelled) return;

      const { data: userData } = await supabase
        .from("users")
        .select("telegram_id")
        .eq("id", user.id)
        .maybeSingle();

      if (cancelled) return;

      if (userData?.telegram_id) {
        setData((d) => ({ ...d, telegramLinked: true }));
        setIsPollingTelegram(false);
      }
    };

    checkLink();
    const interval = setInterval(checkLink, 3000);

    return () => {
      cancelled = true;
      clearInterval(interval);
    };
  }, [isPollingTelegram]);

  // Name save — UPDATE users table
  const handleNameSave = useCallback(async (newName: string) => {
    const supabase = createClient();
    // After Task 27: users.id IS the auth UUID — direct equality, no auth_id column.
    const { error } = await supabase.from("users").update({ name: newName }).eq("id", (await supabase.auth.getUser()).data.user?.id ?? "");
    if (!error) setData((d) => ({ ...d, name: newName, initials: deriveInitials(newName) }));
  }, []);

  // Telegram Link handler
  const handleLinkTelegram = useCallback(async () => {
    setLinkingTelegram(true);
    try {
      const res = await fetch("/api/account/telegram-link", { method: "POST" });
      const json = await res.json();
      if (res.ok && json.launchUrl) {
        setLinkToken(json.token);
        window.open(json.launchUrl, "_blank");
        setIsPollingTelegram(true);
      } else {
        alert(json.error ?? "Failed to initiate Telegram link.");
      }
    } catch (err) {
      console.error("Failed to link Telegram:", err);
      alert("Network error. Please try again.");
    } finally {
      setLinkingTelegram(false);
    }
  }, []);

  // Promo code success — bump balance optimistically
  const handlePromoSuccess = useCallback((added: number) => {
    setData((d) => ({ ...d, balance: d.balance + added }));
  }, []);

  if (data.loading) {
    return (
      <div className="min-h-screen flex items-center justify-center">
        <div className="flex flex-col items-center gap-3 text-muted-foreground">
          <span className="w-6 h-6 rounded-full border-2 border-primary/30 border-t-primary animate-spin" />
          <span className="text-sm font-mono uppercase tracking-wider">Loading account…</span>
        </div>
      </div>
    );
  }

  return (
    <>
      {/* Ambient backdrop — static. Dropped the animate-float + blur-[120px]
          orbs (a perpetual full-layer recomposite for an imperceptible drift)
          in favour of a flat tint + grid. */}
      <div className="fixed inset-0 overflow-hidden pointer-events-none z-0">
        <div
          className="absolute -top-[10%] -left-[5%] w-[35%] h-[35%] rounded-full blur-[60px]"
          style={{ background: "color-mix(in oklab, var(--primary) 6%, transparent)" }}
        />
        <div
          className="absolute bottom-[6%] -right-[6%] w-[30%] h-[30%] rounded-full blur-[60px]"
          style={{ background: "color-mix(in oklab, #9333ea 6%, transparent)" }}
        />
        <div className="absolute inset-0 grid-bg" />
      </div>

      <div className="relative z-10 min-h-screen flex flex-col">
        <SettingsNav />

        <main className="flex-1 w-full max-w-[920px] mx-auto px-4 sm:px-6 py-10">
          <header className="mb-9">
            <div className="text-[10px] font-mono uppercase tracking-[0.22em] text-muted-foreground mb-2">Settings</div>
            <h1 className="text-4xl font-black tracking-tighter leading-tight">Account</h1>
          </header>

          <div className="flex flex-col gap-5">
            <ProfileSection data={data} onNameSave={handleNameSave} />
            <CreditsSection data={data} onPromoSuccess={handlePromoSuccess} />
            <AccountInfoSection data={data} />
            <SecuritySection data={data} linkingTelegram={linkingTelegram} onLinkTelegram={handleLinkTelegram} botUsername={botUsername} isPollingTelegram={isPollingTelegram} linkToken={linkToken} />
            <MiscSection />
            <DangerSection />
          </div>

          <footer className="mt-12 pt-6 border-t border-border flex items-center justify-between gap-4">
            <span className="text-[11px] font-mono uppercase tracking-wider text-muted-foreground">
              Aletheia Travel
            </span>
            <button
              type="button"
              onClick={async () => {
                const supabase = createClient();
                await supabase.auth.signOut();
                window.location.href = "/login";
              }}
              className="inline-flex items-center gap-2 h-9 px-4 rounded-full text-[12px] font-semibold text-muted-foreground hover:text-foreground transition"
              style={{
                background: "color-mix(in oklab, var(--foreground) 5%, transparent)",
                border: "1px solid var(--border)",
              }}
            >
              <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={2} strokeLinecap="round" strokeLinejoin="round" width={14} height={14}>
                <path d="M9 21H5a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h4" />
                <polyline points="16 17 21 12 16 7" />
                <line x1="21" y1="12" x2="9" y2="12" />
              </svg>
              Sign out
            </button>
          </footer>
        </main>
      </div>
    </>
  );
}
