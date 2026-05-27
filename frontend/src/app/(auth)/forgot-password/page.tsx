"use client";

import { useState, useRef } from "react";
import Link from "next/link";
import { Mail, ArrowRight, Loader2, ArrowLeft, Sparkles } from "lucide-react";
import { Turnstile, type TurnstileInstance } from "@marsidev/react-turnstile";
import { createClient } from "@/utils/supabase/client";
import { AuthShell } from "@/components/auth/AuthShell";

const SITE_KEY = process.env.NEXT_PUBLIC_TURNSTILE_SITE_KEY;

function ForgotPasswordMarketing() {
  return (
    <div className="max-w-md">
      <div className="inline-flex items-center gap-2 px-3 py-1 rounded-full bg-primary/10 border border-primary/20 mb-6">
        <Sparkles className="w-3.5 h-3.5 text-primary" />
        <span className="text-xs font-semibold text-primary uppercase tracking-wider">Account recovery</span>
      </div>

      <h1 className="text-4xl xl:text-5xl font-extrabold tracking-tight mb-3 leading-[1.05]">
        We&rsquo;ll get you<br />back on the road.
      </h1>
      <p className="text-base text-muted-foreground mb-10 leading-relaxed">
        Enter your email and we&rsquo;ll send a secure link to reset your password — usually in under a minute.
      </p>

      <ul className="space-y-4">
        {[
          { step: "1", title: "Enter your email below", sub: "The one you used to create your account" },
          { step: "2", title: "Check your inbox", sub: "A reset link arrives within a minute" },
          { step: "3", title: "Set a new password", sub: "Then continue architecting your journey" },
        ].map((row) => (
          <li key={row.step} className="flex items-start gap-3">
            <span className="mt-0.5 w-9 h-9 rounded-xl grid place-items-center flex-shrink-0 bg-primary/10 border border-primary/20 text-sm font-bold text-primary">
              {row.step}
            </span>
            <div>
              <div className="text-sm font-semibold text-foreground">{row.title}</div>
              <div className="text-xs text-muted-foreground">{row.sub}</div>
            </div>
          </li>
        ))}
      </ul>
    </div>
  );
}

function ForgotPasswordForm() {
  const [email, setEmail] = useState("");
  const [emailError, setEmailError] = useState("");
  const [status, setStatus] = useState<"idle" | "loading" | "sent" | "error">("idle");
  const [errorMsg, setErrorMsg] = useState("");
  const turnstileRef = useRef<TurnstileInstance>(null);
  const [captchaToken, setCaptchaToken] = useState<string | null>(SITE_KEY ? null : "");
  const [captchaFailed, setCaptchaFailed] = useState(false);
  const captchaReady = !SITE_KEY || captchaToken !== null;

  const handleSubmit = async (ev: React.FormEvent) => {
    ev.preventDefault();
    if (!email) { setEmailError("Email is required."); return; }
    if (!/^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(email)) { setEmailError("That doesn't look like a valid email."); return; }
    setEmailError("");
    setStatus("loading");

    const supabase = createClient();
    const { error } = await supabase.auth.resetPasswordForEmail(email, {
      redirectTo: `${window.location.origin}/auth/callback?next=/reset-password`,
      ...(SITE_KEY ? { captchaToken: captchaToken ?? "" } : {}),
    });

    turnstileRef.current?.reset();
    setCaptchaToken(SITE_KEY ? null : "");

    if (error) {
      setErrorMsg(error.message);
      setStatus("error");
    } else {
      setStatus("sent");
    }
  };

  if (status === "sent") {
    return (
      <div className="text-center py-4 animate-fade-up">
        <div className="w-12 h-12 rounded-full bg-emerald-500/10 border border-emerald-500/20 grid place-items-center mx-auto mb-4">
          <Mail className="w-6 h-6 text-emerald-500" />
        </div>
        <h3 className="text-lg font-bold text-foreground mb-2">Check your inbox</h3>
        <p className="text-sm text-muted-foreground mb-6">
          We sent a password reset link to <span className="font-semibold text-foreground">{email}</span>.
          The link expires in 1 hour.
        </p>
        <button
          type="button"
          onClick={() => { setStatus("idle"); setEmail(""); }}
          className="text-sm text-primary hover:underline font-medium"
        >
          Send to a different address
        </button>
      </div>
    );
  }

  return (
    <form onSubmit={handleSubmit} noValidate className="w-full">
      <label className="block text-sm font-medium text-foreground/80 mb-2">Email address</label>
      <div className="relative mb-1">
        <Mail className="absolute left-4 top-1/2 -translate-y-1/2 w-[18px] h-[18px] text-muted-foreground pointer-events-none" />
        <input
          type="email"
          inputMode="email"
          autoComplete="email"
          autoFocus
          placeholder="you@example.com"
          value={email}
          onChange={(e) => { setEmail(e.target.value); setEmailError(""); }}
          aria-invalid={!!emailError}
          className="w-full h-12 rounded-full bg-foreground/[0.04] border border-border text-foreground text-[0.95rem] pl-11 pr-4 placeholder:text-muted-foreground hover:border-primary/30 focus:border-primary/60 focus:bg-background outline-none transition-all"
        />
      </div>
      {emailError && (
        <p className="text-xs text-rose-500 dark:text-rose-400 px-2 mt-1 animate-fade-up">{emailError}</p>
      )}

      {SITE_KEY && (
        <div className="mt-5 flex flex-col items-center gap-1.5 w-full overflow-x-auto">
          <Turnstile
            ref={turnstileRef}
            siteKey={SITE_KEY}
            options={{ appearance: "always", theme: "auto" }}
            onSuccess={(token) => { setCaptchaToken(token); setCaptchaFailed(false); }}
            onError={() => { setCaptchaToken(""); setCaptchaFailed(true); }}
            onExpire={() => { setCaptchaToken(null); turnstileRef.current?.reset(); }}
          />
          {captchaFailed && (
            <p className="text-xs text-amber-600 dark:text-amber-400 animate-fade-up">
              Security check failed — please refresh the page.
            </p>
          )}
        </div>
      )}

      <button
        type="submit"
        disabled={status === "loading" || !captchaReady}
        className="mt-6 w-full h-12 rounded-full font-semibold text-base bg-gradient-to-br from-primary to-purple-600 text-white shadow-lg shadow-primary/25 hover:shadow-primary/40 hover:-translate-y-px transition-all disabled:opacity-60 disabled:cursor-not-allowed flex items-center justify-center gap-2"
      >
        {status === "loading"
          ? <><Loader2 className="w-4 h-4 animate-spin" /><span>Sending…</span></>
          : !captchaReady
            ? <><Loader2 className="w-4 h-4 animate-spin" /><span>Security check…</span></>
            : <><span>Send reset link</span><ArrowRight className="w-4 h-4" /></>}
      </button>

      {status === "error" && (
        <div className="mt-4 p-3 rounded-2xl text-sm border animate-fade-up bg-rose-500/10 text-rose-700 dark:text-rose-300 border-rose-500/20">
          {errorMsg}
        </div>
      )}

      <p className="mt-6 text-center text-sm text-muted-foreground">
        Remembered it?{" "}
        <Link href="/login" className="font-semibold text-primary hover:underline">
          Back to sign in
        </Link>
      </p>
    </form>
  );
}

export default function ForgotPasswordPage() {
  return (
    <AuthShell marketingContent={<ForgotPasswordMarketing />}>
      <div className="bg-background/70 backdrop-blur-xl border border-border rounded-[1.75rem] p-8 sm:p-10 shadow-[0_30px_60px_-30px_rgba(0,0,0,0.25)]">
        <Link
          href="/login"
          className="inline-flex items-center gap-1.5 text-sm text-muted-foreground hover:text-foreground transition-colors mb-6"
        >
          <ArrowLeft className="w-4 h-4" /> Back to sign in
        </Link>
        <header className="mb-7">
          <h2 className="text-3xl font-extrabold tracking-tight leading-tight">
            Reset your{" "}
            <span className="bg-gradient-to-r from-blue-600 to-purple-600 bg-clip-text text-transparent animate-gradient-x bg-[length:200%_auto]">
              password.
            </span>
          </h2>
          <p className="text-sm text-muted-foreground mt-1.5">Enter your email and we&apos;ll send a secure link.</p>
        </header>
        <ForgotPasswordForm />
      </div>
    </AuthShell>
  );
}
