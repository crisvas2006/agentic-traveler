"use client";

import { useState, useRef } from "react";
import { useRouter } from "next/navigation";
import Link from "next/link";
import { Sparkles, Mail, Lock, Eye, EyeOff, ArrowRight, Loader2, User, Compass, Check, Zap } from "lucide-react";
import { Turnstile, type TurnstileInstance } from "@marsidev/react-turnstile";
import { createClient } from "@/utils/supabase/client";
import { AuthShell } from "@/components/auth/AuthShell";
import { MIN_PASSWORD_LENGTH } from "@/lib/auth";

/* ── Google logo ── */
function GoogleMark({ size = 18 }: { size?: number }) {
  return (
    <svg width={size} height={size} viewBox="0 0 18 18" aria-hidden="true">
      <path fill="#4285F4" d="M17.64 9.2c0-.64-.06-1.25-.16-1.84H9v3.48h4.84a4.14 4.14 0 0 1-1.8 2.72v2.26h2.92c1.71-1.57 2.7-3.9 2.7-6.62Z"/>
      <path fill="#34A853" d="M9 18c2.43 0 4.47-.8 5.96-2.18l-2.92-2.26c-.81.54-1.84.86-3.04.86-2.34 0-4.32-1.58-5.03-3.7H.92v2.32A9 9 0 0 0 9 18Z"/>
      <path fill="#FBBC05" d="M3.97 10.72A5.4 5.4 0 0 1 3.68 9c0-.6.1-1.18.29-1.72V4.96H.92A9 9 0 0 0 0 9c0 1.45.35 2.82.92 4.04l3.05-2.32Z"/>
      <path fill="#EA4335" d="M9 3.58c1.32 0 2.5.45 3.44 1.35l2.58-2.58A9 9 0 0 0 9 0 9 9 0 0 0 .92 4.96l3.05 2.32C4.68 5.16 6.66 3.58 9 3.58Z"/>
    </svg>
  );
}

/* ── Field error ── */
function FieldError({ msg }: { msg?: string }) {
  if (!msg) return null;
  return <p className="text-xs text-rose-500 dark:text-rose-400 px-2 mt-1 animate-fade-up">{msg}</p>;
}

/* ── Marketing rail content ── */
function SignUpMarketing() {
  const benefits = [
    {
      icon: <Compass className="w-4 h-4 text-primary" />,
      title: "Your Traveler DNA",
      sub: "A personality profile that gets smarter with every trip",
    },
    {
      icon: <Zap className="w-4 h-4 text-primary" />,
      title: "Live trip adaptation",
      sub: "Plans that flex with your mood, weather, and energy",
    },
    {
      icon: <Sparkles className="w-4 h-4 text-primary" />,
      title: "AI-curated itineraries",
      sub: "Day-by-day plans built for you, not the average tourist",
    },
  ];

  return (
    <div className="max-w-md">
      <div className="inline-flex items-center gap-2 px-3 py-1 rounded-full bg-primary/10 border border-primary/20 mb-6">
        <Sparkles className="w-3.5 h-3.5 text-primary" />
        <span className="text-xs font-semibold text-primary uppercase tracking-wider">Early access · free</span>
      </div>

      <h1 className="text-4xl xl:text-5xl font-extrabold tracking-tight mb-3 leading-[1.05]">
        Begin your<br />next journey.
      </h1>
      <p className="text-base text-muted-foreground mb-10 leading-relaxed">
        A travel companion that learns who you are — not just where you want to go.
      </p>

      <ul className="space-y-4">
        {benefits.map((row, i) => (
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

/* ── Sign-up form ── */
const SITE_KEY = process.env.NEXT_PUBLIC_TURNSTILE_SITE_KEY;

function SignUpForm() {
  const router = useRouter();
  const [name, setName] = useState("");
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [confirmPw, setConfirmPw] = useState("");
  const [showPw, setShowPw] = useState(false);
  const [showConfirmPw, setShowConfirmPw] = useState(false);
  const [agreed, setAgreed] = useState(false);
  const [errors, setErrors] = useState<{ name?: string; email?: string; password?: string; confirmPw?: string; agreed?: string }>({});
  const [status, setStatus] = useState<{ kind: "idle" | "loading" | "success" | "error"; message: string; isDuplicate?: boolean }>({ kind: "idle", message: "" });
  const [googleLoading, setGoogleLoading] = useState(false);
  const turnstileRef = useRef<TurnstileInstance>(null);
  const [captchaToken, setCaptchaToken] = useState<string | null>(SITE_KEY ? null : "");
  const [captchaFailed, setCaptchaFailed] = useState(false);

  const captchaReady = !SITE_KEY || captchaToken !== null;

  const validate = () => {
    const e: typeof errors = {};
    if (!name.trim()) e.name = "Name is required.";
    if (!email) e.email = "Email is required.";
    else if (!/^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(email)) e.email = "That doesn't look like a valid email.";
    if (!password) e.password = "Password is required.";
    else if (password.length < MIN_PASSWORD_LENGTH) e.password = `Must be at least ${MIN_PASSWORD_LENGTH} characters.`;
    if (!confirmPw) e.confirmPw = "Please confirm your password.";
    else if (confirmPw !== password) e.confirmPw = "Passwords don't match.";
    if (!agreed) e.agreed = "You must agree to continue.";
    setErrors(e);
    return Object.keys(e).length === 0;
  };

  const handleSubmit = async (ev: React.FormEvent) => {
    ev.preventDefault();
    if (!validate()) return;
    setStatus({ kind: "loading", message: "" });

    const supabase = createClient();
    const { data, error } = await supabase.auth.signUp({
      email,
      password,
      options: {
        data: { full_name: name.trim() },
        ...(SITE_KEY ? { captchaToken: captchaToken ?? "" } : {}),
      },
    });

    turnstileRef.current?.reset();
    setCaptchaToken(SITE_KEY ? null : "");

    if (error) {
      setStatus({ kind: "error", message: error.message });
    } else {
      // Supabase never returns an error for duplicate emails (email enumeration protection).
      // When the email is already confirmed, it returns data.user with identities: [].
      const isDuplicate =
        Array.isArray(data.user?.identities) && data.user.identities.length === 0;
      setStatus({
        kind: "success",
        message: isDuplicate
          ? "duplicate"
          : "A confirmation link is on its way. Click it to activate your account, then sign in.",
        isDuplicate,
      });
    }
  };

  const handleGoogle = async () => {
    setGoogleLoading(true);
    const supabase = createClient();
    await supabase.auth.signInWithOAuth({
      provider: "google",
      options: { redirectTo: `${window.location.origin}/auth/callback` },
    });
  };

  const clearError = (field: keyof typeof errors) =>
    setErrors((prev) => ({ ...prev, [field]: undefined }));

  if (status.kind === "success") {
    if (status.isDuplicate) {
      return (
        <div className="text-center py-4 animate-fade-up">
          <div className="w-12 h-12 rounded-full bg-primary/10 border border-primary/20 grid place-items-center mx-auto mb-4">
            <Mail className="w-6 h-6 text-primary" strokeWidth={2} />
          </div>
          <h3 className="text-lg font-bold text-foreground mb-2">Already have an account?</h3>
          <p className="text-sm text-muted-foreground mb-6">
            This email is already registered. Sign in to pick up where you left off — or reset your password if you've lost access.
          </p>
          <Link
            href="/login"
            className="inline-flex items-center gap-2 h-12 px-6 rounded-full font-semibold text-sm bg-gradient-to-br from-primary to-purple-600 text-white shadow-lg shadow-primary/25 hover:shadow-primary/40 hover:-translate-y-px transition-all"
          >
            Sign in <ArrowRight className="w-4 h-4" />
          </Link>
          <p className="mt-4 text-sm text-muted-foreground">
            <Link href="/forgot-password" className="font-semibold text-primary hover:underline">
              Forgot your password?
            </Link>
          </p>
        </div>
      );
    }

    return (
      <div className="text-center py-4 animate-fade-up">
        <div className="w-12 h-12 rounded-full bg-emerald-500/10 border border-emerald-500/20 grid place-items-center mx-auto mb-4">
          <Check className="w-6 h-6 text-emerald-500" strokeWidth={2.5} />
        </div>
        <h3 className="text-lg font-bold text-foreground mb-2">Check your inbox</h3>
        <p className="text-sm text-muted-foreground mb-6">{status.message}</p>
        <Link
          href="/login"
          className="inline-flex items-center gap-2 h-12 px-6 rounded-full font-semibold text-sm bg-gradient-to-br from-primary to-purple-600 text-white shadow-lg shadow-primary/25 hover:shadow-primary/40 hover:-translate-y-px transition-all"
        >
          Go to sign in <ArrowRight className="w-4 h-4" />
        </Link>
      </div>
    );
  }

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
        <span>or sign up with email</span>
        <span className="flex-1 h-px bg-border" />
      </div>

      {/* Name */}
      <label className="block text-sm font-medium text-foreground/80 mb-2">Full name</label>
      <div className="relative mb-1">
        <User className="absolute left-4 top-1/2 -translate-y-1/2 w-[18px] h-[18px] text-muted-foreground pointer-events-none" />
        <input
          type="text"
          autoComplete="name"
          placeholder="Your name"
          value={name}
          onChange={(e) => { setName(e.target.value); clearError("name"); }}
          aria-invalid={!!errors.name}
          className="w-full h-12 rounded-full bg-foreground/[0.04] border border-border text-foreground text-[0.95rem] pl-11 pr-4 placeholder:text-muted-foreground hover:border-primary/30 focus:border-primary/60 focus:bg-background outline-none transition-all"
        />
      </div>
      <FieldError msg={errors.name} />

      {/* Email */}
      <label className="block text-sm font-medium text-foreground/80 mb-2 mt-5">Email</label>
      <div className="relative mb-1">
        <Mail className="absolute left-4 top-1/2 -translate-y-1/2 w-[18px] h-[18px] text-muted-foreground pointer-events-none" />
        <input
          type="email"
          inputMode="email"
          autoComplete="email"
          placeholder="you@example.com"
          value={email}
          onChange={(e) => { setEmail(e.target.value); clearError("email"); }}
          aria-invalid={!!errors.email}
          className="w-full h-12 rounded-full bg-foreground/[0.04] border border-border text-foreground text-[0.95rem] pl-11 pr-4 placeholder:text-muted-foreground hover:border-primary/30 focus:border-primary/60 focus:bg-background outline-none transition-all"
        />
      </div>
      <FieldError msg={errors.email} />

      {/* Password */}
      <label className="block text-sm font-medium text-foreground/80 mb-2 mt-5">Password</label>
      <div className="relative mb-1">
        <Lock className="absolute left-4 top-1/2 -translate-y-1/2 w-[18px] h-[18px] text-muted-foreground pointer-events-none" />
        <input
          type={showPw ? "text" : "password"}
          autoComplete="new-password"
          placeholder="At least 8 characters"
          value={password}
          onChange={(e) => { setPassword(e.target.value); clearError("password"); clearError("confirmPw"); }}
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

      {/* Confirm password */}
      <label className="block text-sm font-medium text-foreground/80 mb-2 mt-5">Confirm password</label>
      <div className="relative mb-1">
        <Lock className="absolute left-4 top-1/2 -translate-y-1/2 w-[18px] h-[18px] text-muted-foreground pointer-events-none" />
        <input
          type={showConfirmPw ? "text" : "password"}
          autoComplete="new-password"
          placeholder="Repeat your password"
          value={confirmPw}
          onChange={(e) => { setConfirmPw(e.target.value); clearError("confirmPw"); }}
          aria-invalid={!!errors.confirmPw}
          className="w-full h-12 rounded-full bg-foreground/[0.04] border border-border text-foreground text-[0.95rem] pl-11 pr-12 placeholder:text-muted-foreground hover:border-primary/30 focus:border-primary/60 focus:bg-background outline-none transition-all"
        />
        <button
          type="button"
          tabIndex={-1}
          onClick={() => setShowConfirmPw((v) => !v)}
          aria-label={showConfirmPw ? "Hide password" : "Show password"}
          className="absolute right-2 top-1/2 -translate-y-1/2 w-9 h-9 rounded-full grid place-items-center text-muted-foreground hover:text-foreground hover:bg-foreground/5 transition"
        >
          {showConfirmPw ? <EyeOff className="w-[18px] h-[18px]" /> : <Eye className="w-[18px] h-[18px]" />}
        </button>
      </div>
      <FieldError msg={errors.confirmPw} />

      {/* Terms — plain div avoids the label→input double-toggle bug */}
      <div
        className="mt-5 flex items-start gap-2.5 cursor-pointer select-none w-fit"
        onClick={() => { setAgreed((v) => !v); clearError("agreed"); }}
      >
        <span
          className={`mt-0.5 w-5 h-5 rounded-md grid place-items-center transition-all border flex-shrink-0 ${
            agreed
              ? "border-transparent bg-gradient-to-br from-primary to-purple-600"
              : "border-border bg-background"
          }`}
        >
          {agreed && <Check className="w-3 h-3 text-white" strokeWidth={3} />}
        </span>
        <span className="text-sm text-foreground/80 leading-snug">
          I agree to the{" "}
          <Link
            href="/terms"
            className="text-primary hover:underline font-medium"
            onClick={(e) => e.stopPropagation()}
          >Terms of Service</Link>
          {" "}and{" "}
          <Link
            href="/privacy"
            className="text-primary hover:underline font-medium"
            onClick={(e) => e.stopPropagation()}
          >Privacy Policy</Link>
        </span>
      </div>
      <FieldError msg={errors.agreed} />

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

      <button
        type="submit"
        disabled={status.kind === "loading" || !captchaReady}
        className="mt-6 w-full h-12 rounded-full font-semibold text-base bg-gradient-to-br from-primary to-purple-600 text-white shadow-lg shadow-primary/25 hover:shadow-primary/40 hover:-translate-y-px transition-all disabled:opacity-60 disabled:cursor-not-allowed flex items-center justify-center gap-2"
      >
        {status.kind === "loading"
          ? <><Loader2 className="w-4 h-4 animate-spin" /><span>Creating account…</span></>
          : !captchaReady
          ? <><Loader2 className="w-4 h-4 animate-spin" /><span>Security check…</span></>
          : <><span>Create account</span><ArrowRight className="w-4 h-4" /></>}
      </button>

      {/* Error banner */}
      {status.kind === "error" && (
        <div className="mt-4 p-3 rounded-2xl text-sm border animate-fade-up bg-rose-500/10 text-rose-700 dark:text-rose-300 border-rose-500/20">
          {status.message}
        </div>
      )}

      <p className="mt-6 text-center text-sm text-muted-foreground">
        Already have an account?{" "}
        <Link href="/login" className="font-semibold text-primary hover:underline">
          Sign in
        </Link>
      </p>
    </form>
  );
}

/* ── Page ── */
export default function SignUpPage() {
  return (
    <AuthShell marketingContent={<SignUpMarketing />}>
      <div className="bg-background/70 backdrop-blur-xl border border-border rounded-[1.75rem] p-8 sm:p-10 shadow-[0_30px_60px_-30px_rgba(0,0,0,0.25)]">
        <header className="mb-7">
          <h2 className="text-3xl font-extrabold tracking-tight leading-tight">
            Create your{" "}
            <span className="bg-gradient-to-r from-blue-600 to-purple-600 bg-clip-text text-transparent animate-gradient-x bg-[length:200%_auto]">
              account.
            </span>
          </h2>
          <p className="text-sm text-muted-foreground mt-1.5">Start architecting journeys built around you.</p>
        </header>
        <SignUpForm />
      </div>
    </AuthShell>
  );
}
