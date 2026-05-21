"use client";

import { useState, useRef } from "react";
import { useRouter } from "next/navigation";
import Link from "next/link";
import { Lock, Eye, EyeOff, ArrowRight, Loader2, Check, Sparkles } from "lucide-react";
import { Turnstile, type TurnstileInstance } from "@marsidev/react-turnstile";
import { createClient } from "@/utils/supabase/client";
import { AuthShell } from "@/components/auth/AuthShell";

const SITE_KEY = process.env.NEXT_PUBLIC_TURNSTILE_SITE_KEY;

function ResetPasswordMarketing() {
  return (
    <div className="max-w-md">
      <div className="inline-flex items-center gap-2 px-3 py-1 rounded-full bg-primary/10 border border-primary/20 mb-6">
        <Sparkles className="w-3.5 h-3.5 text-primary" />
        <span className="text-xs font-semibold text-primary uppercase tracking-wider">Almost there</span>
      </div>
      <h1 className="text-4xl xl:text-5xl font-extrabold tracking-tight mb-3 leading-[1.05]">
        Choose a new<br />password.
      </h1>
      <p className="text-base text-muted-foreground leading-relaxed">
        Pick something strong. Your journeys and Traveler DNA will be waiting on the other side.
      </p>
    </div>
  );
}

function ResetPasswordForm() {
  const router = useRouter();
  const [password, setPassword] = useState("");
  const [confirmPw, setConfirmPw] = useState("");
  const [showPw, setShowPw] = useState(false);
  const [showConfirm, setShowConfirm] = useState(false);
  const [errors, setErrors] = useState<{ password?: string; confirmPw?: string }>({});
  const [status, setStatus] = useState<"idle" | "loading" | "success" | "error">("idle");
  const [errorMsg, setErrorMsg] = useState("");
  const turnstileRef = useRef<TurnstileInstance>(null);
  const [captchaToken, setCaptchaToken] = useState<string | null>(SITE_KEY ? null : "");
  const [captchaFailed, setCaptchaFailed] = useState(false);
  const captchaReady = !SITE_KEY || captchaToken !== null;

  const validate = () => {
    const e: typeof errors = {};
    if (!password) e.password = "Password is required.";
    else if (password.length < 8) e.password = "Must be at least 8 characters.";
    if (!confirmPw) e.confirmPw = "Please confirm your password.";
    else if (confirmPw !== password) e.confirmPw = "Passwords don't match.";
    setErrors(e);
    return Object.keys(e).length === 0;
  };

  const handleSubmit = async (ev: React.FormEvent) => {
    ev.preventDefault();
    if (!validate()) return;
    setStatus("loading");

    const supabase = createClient();
    const { error } = await supabase.auth.updateUser({ password });

    if (error) {
      setErrorMsg(error.message);
      setStatus("error");
    } else {
      setStatus("success");
      setTimeout(() => router.push("/"), 2000);
    }
  };

  if (status === "success") {
    return (
      <div className="text-center py-4 animate-fade-up">
        <div className="w-12 h-12 rounded-full bg-emerald-500/10 border border-emerald-500/20 grid place-items-center mx-auto mb-4">
          <Check className="w-6 h-6 text-emerald-500" strokeWidth={2.5} />
        </div>
        <h3 className="text-lg font-bold text-foreground mb-2">Password updated</h3>
        <p className="text-sm text-muted-foreground">Redirecting you to your journeys…</p>
      </div>
    );
  }

  return (
    <form onSubmit={handleSubmit} noValidate className="w-full">
      {/* New password */}
      <label className="block text-sm font-medium text-foreground/80 mb-2">New password</label>
      <div className="relative mb-1">
        <Lock className="absolute left-4 top-1/2 -translate-y-1/2 w-[18px] h-[18px] text-muted-foreground pointer-events-none" />
        <input
          type={showPw ? "text" : "password"}
          autoComplete="new-password"
          autoFocus
          placeholder="At least 8 characters"
          value={password}
          onChange={(e) => { setPassword(e.target.value); setErrors((p) => ({ ...p, password: undefined })); }}
          aria-invalid={!!errors.password}
          className="w-full h-12 rounded-full bg-foreground/[0.04] border border-border text-foreground text-[0.95rem] pl-11 pr-12 placeholder:text-muted-foreground hover:border-primary/30 focus:border-primary/60 focus:bg-background outline-none transition-all"
        />
        <button
          type="button"
          tabIndex={-1}
          onClick={() => setShowPw((v) => !v)}
          aria-label={showPw ? "Hide password" : "Show password"}
          className="absolute right-2 top-1/2 -translate-y-1/2 w-9 h-9 rounded-full grid place-items-center text-muted-foreground hover:text-foreground hover:bg-foreground/5 transition"
        >
          {showPw ? <EyeOff className="w-[18px] h-[18px]" /> : <Eye className="w-[18px] h-[18px]" />}
        </button>
      </div>
      {errors.password && <p className="text-xs text-rose-500 dark:text-rose-400 px-2 mt-1 animate-fade-up">{errors.password}</p>}

      {/* Confirm password */}
      <label className="block text-sm font-medium text-foreground/80 mb-2 mt-5">Confirm new password</label>
      <div className="relative mb-1">
        <Lock className="absolute left-4 top-1/2 -translate-y-1/2 w-[18px] h-[18px] text-muted-foreground pointer-events-none" />
        <input
          type={showConfirm ? "text" : "password"}
          autoComplete="new-password"
          placeholder="Repeat your new password"
          value={confirmPw}
          onChange={(e) => { setConfirmPw(e.target.value); setErrors((p) => ({ ...p, confirmPw: undefined })); }}
          aria-invalid={!!errors.confirmPw}
          className="w-full h-12 rounded-full bg-foreground/[0.04] border border-border text-foreground text-[0.95rem] pl-11 pr-12 placeholder:text-muted-foreground hover:border-primary/30 focus:border-primary/60 focus:bg-background outline-none transition-all"
        />
        <button
          type="button"
          tabIndex={-1}
          onClick={() => setShowConfirm((v) => !v)}
          aria-label={showConfirm ? "Hide password" : "Show password"}
          className="absolute right-2 top-1/2 -translate-y-1/2 w-9 h-9 rounded-full grid place-items-center text-muted-foreground hover:text-foreground hover:bg-foreground/5 transition"
        >
          {showConfirm ? <EyeOff className="w-[18px] h-[18px]" /> : <Eye className="w-[18px] h-[18px]" />}
        </button>
      </div>
      {errors.confirmPw && <p className="text-xs text-rose-500 dark:text-rose-400 px-2 mt-1 animate-fade-up">{errors.confirmPw}</p>}

      {SITE_KEY && (
        <div className="mt-5 flex flex-col items-center gap-1.5">
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
          ? <><Loader2 className="w-4 h-4 animate-spin" /><span>Updating…</span></>
          : !captchaReady
            ? <><Loader2 className="w-4 h-4 animate-spin" /><span>Security check…</span></>
            : <><span>Set new password</span><ArrowRight className="w-4 h-4" /></>}
      </button>

      {status === "error" && (
        <div className="mt-4 p-3 rounded-2xl text-sm border animate-fade-up bg-rose-500/10 text-rose-700 dark:text-rose-300 border-rose-500/20">
          {errorMsg}
        </div>
      )}

      <p className="mt-6 text-center text-sm text-muted-foreground">
        <Link href="/login" className="font-semibold text-primary hover:underline">Back to sign in</Link>
      </p>
    </form>
  );
}

export default function ResetPasswordPage() {
  return (
    <AuthShell marketingContent={<ResetPasswordMarketing />}>
      <div className="bg-background/70 backdrop-blur-xl border border-border rounded-[1.75rem] p-8 sm:p-10 shadow-[0_30px_60px_-30px_rgba(0,0,0,0.25)]">
        <header className="mb-7">
          <h2 className="text-3xl font-extrabold tracking-tight leading-tight">
            New{" "}
            <span className="bg-gradient-to-r from-blue-600 to-purple-600 bg-clip-text text-transparent animate-gradient-x bg-[length:200%_auto]">
              password.
            </span>
          </h2>
          <p className="text-sm text-muted-foreground mt-1.5">Choose something strong — 8 characters or more.</p>
        </header>
        <ResetPasswordForm />
      </div>
    </AuthShell>
  );
}
