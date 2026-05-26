"use client";

import { useState, useRef } from "react";
import { useRouter } from "next/navigation";
import Link from "next/link";
import { Sparkles, Mail, Lock, Eye, EyeOff, ArrowRight, Loader2, Compass, Check } from "lucide-react";
import { Turnstile, type TurnstileInstance } from "@marsidev/react-turnstile";
import { createBrowserClient } from "@supabase/ssr";
import { AuthShell } from "@/components/auth/AuthShell";
import { MIN_PASSWORD_LENGTH } from "@/lib/auth";

/* ── Google logo ── */
function GoogleMark({ size = 18 }: { size?: number }) {
  return (
    <svg width={size} height={size} viewBox="0 0 18 18" aria-hidden="true">
      <path fill="#4285F4" d="M17.64 9.2c0-.64-.06-1.25-.16-1.84H9v3.48h4.84a4.14 4.14 0 0 1-1.8 2.72v2.26h2.92c1.71-1.57 2.7-3.9 2.7-6.62Z" />
      <path fill="#34A853" d="M9 18c2.43 0 4.47-.8 5.96-2.18l-2.92-2.26c-.81.54-1.84.86-3.04.86-2.34 0-4.32-1.58-5.03-3.7H.92v2.32A9 9 0 0 0 9 18Z" />
      <path fill="#FBBC05" d="M3.97 10.72A5.4 5.4 0 0 1 3.68 9c0-.6.1-1.18.29-1.72V4.96H.92A9 9 0 0 0 0 9c0 1.45.35 2.82.92 4.04l3.05-2.32Z" />
      <path fill="#EA4335" d="M9 3.58c1.32 0 2.5.45 3.44 1.35l2.58-2.58A9 9 0 0 0 9 0 9 9 0 0 0 .92 4.96l3.05 2.32C4.68 5.16 6.66 3.58 9 3.58Z" />
    </svg>
  );
}

/* ── Field error ── */
function FieldError({ msg }: { msg?: string }) {
  if (!msg) return null;
  return <p className="text-xs text-rose-500 dark:text-rose-400 px-2 mt-1 animate-fade-up">{msg}</p>;
}

/* ── Marketing rail content ── */
function LoginMarketing() {
  const stats = [
    { icon: <Compass className="w-4 h-4 text-primary" />, title: "3 active journeys", sub: "Kyoto · Patagonia · Lisbon weekend" },
    { icon: <Sparkles className="w-4 h-4 text-primary" />, title: "12 new matches", sub: "Suggestions tuned to your mood this week" },
    { icon: <Check className="w-4 h-4 text-primary" />, title: "Live adaptation on", sub: "Telegram check-ins enabled" },
  ];

  return (
    <div className="max-w-md">
      <div className="inline-flex items-center gap-2 px-3 py-1 rounded-full bg-primary/10 border border-primary/20 mb-6">
        <Sparkles className="w-3.5 h-3.5 text-primary" />
        <span className="text-xs font-semibold text-primary uppercase tracking-wider">Alpha · Welcome back</span>
      </div>

      <h1 className="text-4xl xl:text-5xl font-extrabold tracking-tight mb-3 leading-[1.05]">
        Pick up where<br />your journey paused.
      </h1>
      <p className="text-base text-muted-foreground mb-10 leading-relaxed">
        Your Traveler DNA, saved itineraries, and live trip adaptations — all waiting on the other side of this form.
      </p>

      <ul className="space-y-4">
        {stats.map((row, i) => (
          <li key={i} className="flex items-start gap-3">
            <span className="mt-0.5 w-9 h-9 rounded-xl grid place-items-center flex-shrink-0 bg-primary/10 border border-primary/20">
              {row.icon}
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

/* ── Login form ── */
const SITE_KEY = process.env.NEXT_PUBLIC_TURNSTILE_SITE_KEY;

function LoginForm() {
  const router = useRouter();
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [showPw, setShowPw] = useState(false);
  const [remember, setRemember] = useState(true);
  const [errors, setErrors] = useState<{ email?: string; password?: string }>({});
  const [status, setStatus] = useState<{ kind: "idle" | "loading" | "success" | "error"; message: string }>({ kind: "idle", message: "" });
  const [googleLoading, setGoogleLoading] = useState(false);
  const turnstileRef = useRef<TurnstileInstance>(null);
  // null = widget still loading; string = resolved (valid token, or "" on error/expire)
  const [captchaToken, setCaptchaToken] = useState<string | null>(SITE_KEY ? null : "");
  const [captchaFailed, setCaptchaFailed] = useState(false);

  // Only block submit while the widget is genuinely pending (null).
  // An error/expire ("") unblocks so the user sees a useful Supabase message.
  const captchaReady = !SITE_KEY || captchaToken !== null;

  const validate = () => {
    const e: typeof errors = {};
    if (!email) e.email = "Email is required.";
    else if (!/^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(email)) e.email = "That doesn't look like a valid email.";
    if (!password) e.password = "Password is required.";
    else if (password.length < MIN_PASSWORD_LENGTH) e.password = `Must be at least ${MIN_PASSWORD_LENGTH} characters.`;
    setErrors(e);
    return Object.keys(e).length === 0;
  };

  const handleSubmit = async (ev: React.FormEvent) => {
    ev.preventDefault();
    if (!validate()) return;
    setStatus({ kind: "loading", message: "" });

    // "Remember me" controls session persistence:
    //   checked  → localStorage (survives browser restart) — default Supabase behaviour
    //   unchecked → sessionStorage (cleared when the tab/window closes)
    const url = process.env.NEXT_PUBLIC_SUPABASE_URL!;
    const key = process.env.NEXT_PUBLIC_SUPABASE_PUBLISHABLE_KEY!;
    const supabase = remember
      ? createBrowserClient(url, key)
      : createBrowserClient(url, key, {
          auth: {
            storage: {
              getItem: (k: string) => sessionStorage.getItem(k),
              setItem: (k: string, v: string) => sessionStorage.setItem(k, v),
              removeItem: (k: string) => sessionStorage.removeItem(k),
            },
          },
        });

    const { error } = await supabase.auth.signInWithPassword({
      email,
      password,
      options: SITE_KEY ? { captchaToken: captchaToken ?? "" } : undefined,
    });

    // Reset widget — Cloudflare tokens are single-use
    turnstileRef.current?.reset();
    setCaptchaToken(SITE_KEY ? null : "");

    if (error) {
      setStatus({ kind: "error", message: error.message });
    } else {
      setStatus({ kind: "success", message: "Signed in — redirecting to your journeys…" });
      router.push("/dashboard");
      router.refresh();
    }
  };

  const handleGoogle = async () => {
    setGoogleLoading(true);
    const supabase = createBrowserClient(
      process.env.NEXT_PUBLIC_SUPABASE_URL!,
      process.env.NEXT_PUBLIC_SUPABASE_PUBLISHABLE_KEY!,
    );
    await supabase.auth.signInWithOAuth({
      provider: "google",
      options: { redirectTo: `${window.location.origin}/auth/callback` },
    });
    // Browser will redirect; loading state stays until navigation
  };

  return (
    <form onSubmit={handleSubmit} noValidate className="w-full">
      {/* Google */}
      <button
        type="button"
        onClick={handleGoogle}
        disabled={googleLoading}
        className="w-full h-12 rounded-full font-semibold bg-background border border-border text-foreground hover:bg-muted hover:border-primary/30 transition-all flex items-center justify-center gap-2.5 disabled:opacity-60 disabled:cursor-not-allowed"
      >
        {googleLoading
          ? <Loader2 className="w-4 h-4 animate-spin" />
          : <GoogleMark />}
        <span>Continue with Google</span>
      </button>

      {/* Divider */}
      <div className="flex items-center gap-3 my-6 text-xs text-muted-foreground uppercase tracking-widest">
        <span className="flex-1 h-px bg-border" />
        <span>or sign in with email</span>
        <span className="flex-1 h-px bg-border" />
      </div>

      {/* Email */}
      <label className="block text-sm font-medium text-foreground/80 mb-2">Email</label>
      <div className="relative mb-1">
        <Mail className="absolute left-4 top-1/2 -translate-y-1/2 w-[18px] h-[18px] text-muted-foreground pointer-events-none" />
        <input
          type="email"
          inputMode="email"
          autoComplete="email"
          placeholder="you@example.com"
          value={email}
          onChange={(e) => { setEmail(e.target.value); if (errors.email) setErrors({ ...errors, email: undefined }); }}
          aria-invalid={!!errors.email}
          className="w-full h-12 rounded-full bg-foreground/[0.04] border border-border text-foreground text-[0.95rem] pl-11 pr-4 placeholder:text-muted-foreground hover:border-primary/30 focus:border-primary/60 focus:bg-background outline-none transition-all"
        />
      </div>
      <FieldError msg={errors.email} />

      {/* Password */}
      <div className="flex items-baseline justify-between mt-5 mb-2">
        <label className="text-sm font-medium text-foreground/80">Password</label>
        <Link href="/forgot-password" className="text-xs font-semibold text-primary hover:underline">Forgot?</Link>
      </div>
      <div className="relative mb-1">
        <Lock className="absolute left-4 top-1/2 -translate-y-1/2 w-[18px] h-[18px] text-muted-foreground pointer-events-none" />
        <input
          type={showPw ? "text" : "password"}
          autoComplete="current-password"
          placeholder="Enter your password"
          value={password}
          onChange={(e) => { setPassword(e.target.value); if (errors.password) setErrors({ ...errors, password: undefined }); }}
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
      <FieldError msg={errors.password} />

      {/* Remember me */}
      <label className="mt-5 flex items-center gap-2.5 cursor-pointer select-none w-fit">
        <span
          className={`w-5 h-5 rounded-md grid place-items-center transition-all border flex-shrink-0 ${remember
              ? "border-transparent bg-gradient-to-br from-primary to-purple-600"
              : "border-border bg-background"
            }`}
        >
          {remember && <Check className="w-3 h-3 text-white" strokeWidth={3} />}
        </span>
        <input
          type="checkbox"
          checked={remember}
          onChange={(e) => setRemember(e.target.checked)}
          className="sr-only"
        />
        <span className="text-sm text-foreground/80">Keep me signed in</span>
      </label>

      {/* Turnstile CAPTCHA — always visible so users know the form is protected */}
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

      {/* Submit — shows spinner only while widget is genuinely pending */}
      <button
        type="submit"
        disabled={status.kind === "loading" || !captchaReady}
        className="mt-6 w-full h-12 rounded-full font-semibold text-base bg-gradient-to-br from-primary to-purple-600 text-white shadow-lg shadow-primary/25 hover:shadow-primary/40 hover:-translate-y-px transition-all disabled:opacity-60 disabled:cursor-not-allowed flex items-center justify-center gap-2"
      >
        {status.kind === "loading"
          ? <><Loader2 className="w-4 h-4 animate-spin" /><span>Signing in…</span></>
          : !captchaReady
            ? <><Loader2 className="w-4 h-4 animate-spin" /><span>Security check…</span></>
            : <><span>Sign in</span><ArrowRight className="w-4 h-4" /></>}
      </button>

      {/* Status banner */}
      {(status.kind === "success" || status.kind === "error") && (
        <div className={`mt-4 p-3 rounded-2xl text-sm border animate-fade-up ${status.kind === "success"
            ? "bg-emerald-500/10 text-emerald-700 dark:text-emerald-300 border-emerald-500/20"
            : "bg-rose-500/10 text-rose-700 dark:text-rose-300 border-rose-500/20"
          }`}>
          {status.message}
        </div>
      )}

      <p className="mt-6 text-center text-sm text-muted-foreground">
        New to Aletheia?{" "}
        <Link href="/sign-up" className="font-semibold text-primary hover:underline">
          Create an account
        </Link>
      </p>
    </form>
  );
}

/* ── Page ── */
export default function LoginPage() {
  return (
    <AuthShell marketingContent={<LoginMarketing />}>
      <div className="bg-background/70 backdrop-blur-xl border border-border rounded-[1.75rem] p-8 sm:p-10 shadow-[0_30px_60px_-30px_rgba(0,0,0,0.25)]">
        <header className="mb-7">
          <h2 className="text-3xl font-extrabold tracking-tight leading-tight">
            Welcome{" "}
            <span className="bg-gradient-to-r from-blue-600 to-purple-600 bg-clip-text text-transparent animate-gradient-x bg-[length:200%_auto]">
              back.
            </span>
          </h2>
          <p className="text-sm text-muted-foreground mt-1.5">Sign in to continue architecting your journey.</p>
        </header>
        <LoginForm />
      </div>
    </AuthShell>
  );
}
