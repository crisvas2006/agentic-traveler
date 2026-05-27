"use client";

import * as React from "react";
import { useState } from "react";
import { cn } from "@/lib/utils";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Sparkles, Compass, Zap, Shield, ArrowRight, Calendar } from "lucide-react";

import { PageWrapper } from "@/components/layout/PageWrapper";
import { Reveal } from "@/components/ui/Reveal";

// Hero Section Component
function HeroSection() {
  return (
    <section className="relative min-h-[calc(100vh-64px)] flex flex-col items-center justify-center overflow-hidden py-12">
      <div className="container mx-auto px-4 relative z-10">
        <Reveal className="max-w-4xl mx-auto text-center">
          <div className="inline-flex items-center gap-2 px-3 py-1 rounded-full bg-primary/10 border border-primary/20 backdrop-blur-sm mb-8">
            <Sparkles className="w-3.5 h-3.5 text-primary" />
            <span className="text-xs font-semibold text-primary uppercase tracking-wider">Early access — 100 seats</span>
          </div>

          <h1 className="text-5xl md:text-6xl font-extrabold tracking-tight mb-4 leading-tight">
            Don&rsquo;t book a trip.<br />Architect a journey.
          </h1>

          <p className="text-lg md:text-xl text-muted-foreground mb-8 max-w-2xl mx-auto leading-relaxed">
            Travel planning that adapts to who you actually are — built around your{" "}
            <span className="bg-gradient-to-r from-blue-600 to-purple-600 bg-clip-text text-transparent font-semibold">
              Traveler DNA
            </span>
            , not the average.
          </p>

          <div className="flex flex-col sm:flex-row gap-4 justify-center items-center">
            <Button
              size="lg"
              className="text-base px-6 h-12 rounded-full shadow-lg shadow-primary/25 hover:shadow-primary/40 transition-all hover:scale-105"
              onClick={() => {
                const emailInput = document.getElementById('email-input');
                if (emailInput) {
                  emailInput.scrollIntoView({ behavior: 'smooth', block: 'center' });
                  setTimeout(() => emailInput.focus(), 500);
                }
              }}
            >
              Get early access
              <ArrowRight className="ml-2 w-4 h-4" />
            </Button>
            <Button
              size="lg"
              variant="outline"
              className="text-base px-6 h-12 rounded-full border-border hover:bg-muted/50"
              onClick={() => {
                document.getElementById('proof-section-bg')?.scrollIntoView({ behavior: 'smooth', block: 'start' });
              }}
            >
              See how it works
            </Button>
          </div>
        </Reveal>
      </div>

      {/* Scroll Indicator - Hidden on mobile as it overlaps content */}
      <div className="relative mt-12 animate-bounce hidden md:block">
        <div className="w-6 h-10 border-2 border-foreground/30 rounded-full flex justify-center">
          <div className="w-1 h-3 bg-foreground/50 rounded-full mt-2 animate-pulse" />
        </div>
      </div>
    </section>
  );
}

// Proof Section Component
function ProofSection() {
  const roadmap = [
    {
      phase: "Available now",
      title: "Discovery & planning",
      description: "Vague requests in, real itineraries out. Realtime weather and events baked in.",
      active: true
    },
    {
      phase: "Upcoming",
      title: "Interactive itineraries",
      description: "Day-by-day plans with alternates for tired days, rainy days, and second-wind days.",
      active: false
    },
    {
      phase: "Future vision",
      title: "Seamless & social",
      description: "Trips with friends. Auto-booking. Quiet matching for travelers who fit.",
      active: false
    },
  ];

  return (
    <section id="proof-section" className="min-h-[calc(100vh-64px)] flex flex-col justify-center py-32 relative overflow-hidden scroll-mt-16">
      <div id="proof-section-bg" className="absolute inset-0 bg-[radial-gradient(circle_at_center,rgba(59,130,246,0.05)_0%,transparent_70%)]" />

      <div className="container mx-auto px-4 relative z-10">
        <Reveal className="text-center mb-16">
          <h2 className="text-3xl md:text-4xl font-bold tracking-tight mb-8">
            Built for the trip
            <br />
            <span className="bg-gradient-to-r from-blue-600 to-purple-600 bg-clip-text text-transparent">only you would take</span>
          </h2>

          <p className="text-base md:text-lg text-muted-foreground mb-12 max-w-3xl mx-auto leading-relaxed">
            Most platforms solve for the cheapest flight or the trendiest hotel. Aletheia solves for the person. A travel companion that reads your energy, your motivations, and the season of life you&rsquo;re in — and plans accordingly.
          </p>
        </Reveal>

        <div className="grid md:grid-cols-3 gap-6 max-w-5xl mx-auto">
          {roadmap.map((item, index) => (
            <div
              key={index}
              className={cn(
                "relative p-6 rounded-2xl border backdrop-blur-sm transition-all hover:scale-105",
                item.active
                  ? "bg-primary/10 border-primary/30 shadow-lg shadow-primary/5"
                  : "bg-muted border-border hover:bg-background hover:border-primary/20"
              )}
            >
              {item.active && (
                <div className="absolute -top-3 -right-3">
                  <span className="relative flex h-5 w-5">
                    <span className="animate-ping absolute inline-flex h-full w-full rounded-full bg-primary/40 opacity-75"></span>
                    <span className="relative inline-flex rounded-full h-5 w-5 bg-primary items-center justify-center">
                      <Sparkles className="w-2.5 h-2.5 text-white" />
                    </span>
                  </span>
                </div>
              )}
              <div className={cn(
                "text-xs font-semibold mb-2 uppercase tracking-wider",
                item.active ? "text-primary" : "text-muted-foreground"
              )}>
                {item.phase}
              </div>
              <h3 className="text-xl font-bold text-foreground mb-3">{item.title}</h3>
              <p className="text-sm text-muted-foreground leading-relaxed">{item.description}</p>
            </div>
          ))}
        </div>
      </div>
    </section>
  );
}

// Features Section Component
function FeaturesSection() {
  const features = [
    {
      icon: Compass,
      title: "Intuitive discovery",
      description: "Say “five days in late spring, feeling tired, want nature and culture.” Get back a shortlist that fits.",
      color: "from-purple-500 to-violet-500",
    },
    {
      icon: Calendar,
      title: "Flexible itineraries",
      description: "Day-level plans with alternates for low-energy mornings, weather curveballs, and unexpected second winds.",
      color: "from-violet-500 to-purple-500",
    },
    {
      icon: Zap,
      title: "Live adaptation",
      description: "Mid-trip, message us on Telegram. Plans bend in real time — no replanning your whole week.",
      color: "from-purple-600 to-violet-600",
    },
    {
      icon: Shield,
      title: "Traveler DNA",
      description: "Odyssey Onboarding builds your Traveler DNA — 15 dimensions of how you actually like to travel. Every suggestion runs through it.",
      color: "from-violet-600 to-purple-600",
    },
  ];

  return (
    <section className="py-20 relative overflow-hidden">
      <div className="absolute inset-0">
        <div className="absolute top-0 left-1/4 w-80 h-80 bg-primary/5 rounded-full blur-[100px]" />
        <div className="absolute bottom-0 right-1/4 w-80 h-80 bg-purple-600/5 rounded-full blur-[100px]" />
      </div>

      <div className="container mx-auto px-4 relative z-10">
        <Reveal className="text-center mb-12">
          <h2 className="text-3xl md:text-4xl font-bold mb-4 tracking-tight">
            How the companion works
          </h2>
          <p className="text-base text-muted-foreground max-w-2xl mx-auto">
            Planning that adapts to you, not the other way around.
          </p>
        </Reveal>

        <div className="grid md:grid-cols-2 gap-6 max-w-6xl mx-auto">
          {features.map((feature, index) => {
            const Icon = feature.icon;
            return (
              <div
                key={index}
                className="group p-6 rounded-2xl bg-muted/50 border border-border backdrop-blur-sm transition-all hover:bg-background hover:border-primary/30 hover:scale-105 hover:shadow-xl hover:shadow-primary/5"
              >
                <div className={cn("w-12 h-12 rounded-xl bg-gradient-to-br flex items-center justify-center mb-5 group-hover:scale-110 transition-transform", feature.color)}>
                  <Icon className="w-6 h-6 text-white" />
                </div>
                <h3 className="text-xl font-bold text-foreground mb-3">{feature.title}</h3>
                <p className="text-sm text-muted-foreground leading-relaxed">{feature.description}</p>
              </div>
            );
          })}
        </div>

        {/* Problem Statement */}
        <div className="mt-16 max-w-4xl mx-auto p-6 rounded-2xl bg-primary/5 border border-primary/10 backdrop-blur-sm">
          <h3 className="text-xl font-bold text-foreground mb-3">The problem with static planning</h3>
          <p className="text-sm text-muted-foreground leading-relaxed">
            Hours lost across blogs, Reddit threads, and booking sites — and the trip you end up with was picked for price, not fit. By day three, you&rsquo;re overscheduled, the weather turned, and there&rsquo;s no plan B.
          </p>
        </div>
      </div>
    </section>
  );
}

import { signupForAlpha } from "./actions";
import { createClient as createBrowserSupabase } from "@/utils/supabase/client";
import { ALPHA_CAP } from "@/lib/alpha-config";

// CTA Section Component
function CTASection() {
  const [status, setStatus] = useState<{ type: 'success' | 'error' | null, message: string }>({ type: null, message: "" });
  const [isPending, setIsPending] = useState(false);
  const [cooldown, setCooldown] = useState(0);
  // null = not yet loaded or fetch failed → render static fallback copy
  const [seatsTaken, setSeatsTaken] = useState<number | null>(null);

  // Fetch the live waitlist count on mount. Anon role can read row count via
  // the `waitlist_count_anon` RLS policy + column-level grant on (id, created_at).
  // On any failure we silently fall back to the static "100 seats" copy.
  React.useEffect(() => {
    let cancelled = false;
    (async () => {
      try {
        const supabase = createBrowserSupabase();
        const { count, error } = await supabase
          .from("waitlist")
          .select("id", { count: "exact", head: true });
        if (cancelled) return;
        if (error || count === null) {
          setSeatsTaken(null);
        } else {
          setSeatsTaken(count);
        }
      } catch {
        if (!cancelled) setSeatsTaken(null);
      }
    })();
    return () => { cancelled = true; };
  }, []);

  // Check initial cooldown on mount
  React.useEffect(() => {
    const lastSubmitStr = localStorage.getItem('aletheia_lastSignup');
    if (lastSubmitStr) {
      const lastSubmitTime = parseInt(lastSubmitStr, 10);
      const timeSinceLastSubmit = Date.now() - lastSubmitTime;
      if (timeSinceLastSubmit < 60000) {
        setCooldown(Math.ceil((60000 - timeSinceLastSubmit) / 1000));
      }
    }
  }, []);

  // Live countdown timer
  React.useEffect(() => {
    if (cooldown <= 0) {
      if (status.type === 'error' && status.message.includes('wait')) {
        setStatus({ type: null, message: "" }); // Clear rate limit error when done
      }
      return;
    }
    const timer = setInterval(() => {
      setCooldown(prev => prev - 1);
    }, 1000);
    return () => clearInterval(timer);
  }, [cooldown, status]);

  const handleSubmit = async (e: React.FormEvent<HTMLFormElement>) => {
    e.preventDefault();

    if (cooldown > 0) {
      setStatus({ type: 'error', message: `Hold up — wait ${cooldown}s and try again.` });
      return;
    }

    setIsPending(true);
    setStatus({ type: null, message: "" });

    const formData = new FormData(e.currentTarget);
    const result = await signupForAlpha(formData);

    if (result.success) {
      localStorage.setItem('aletheia_lastSignup', Date.now().toString());
      setCooldown(30); // Start 60s cooldown
      setStatus({ type: 'success', message: result.message });
      (e.target as HTMLFormElement).reset();
    } else {
      setStatus({ type: 'error', message: result.message });
    }
    setIsPending(false);
  };

  return (
    <section className="pt-32 pb-24 bg-gradient-to-br from-blue-600 to-purple-600 text-white relative overflow-hidden">
      <div className="absolute inset-0">
        <div className="absolute top-1/2 left-1/2 -translate-x-1/2 -translate-y-1/2 w-[600px] h-[600px] bg-white/10 rounded-full blur-[120px] animate-pulse" />
      </div>

      <div className="container mx-auto px-4 relative z-10">
        <div className="max-w-3xl mx-auto text-center">
          <h2 className="text-3xl md:text-4xl font-bold tracking-tight mb-4">
            Stop planning trips.<br />Start architecting journeys.
          </h2>

          <p className="text-base text-white/90 mb-10 leading-relaxed">
            {seatsTaken === null ? (
              <>
                Aletheia opens with {ALPHA_CAP} early-access seats. Drop your email — if you&rsquo;re in the first {ALPHA_CAP}, you&rsquo;ll get sign-in details within 24 hours. Either way, you&rsquo;re on the list.
              </>
            ) : seatsTaken >= ALPHA_CAP ? (
              <>
                Aletheia early access is full. <strong className="text-white">{ALPHA_CAP} of {ALPHA_CAP} seats</strong> taken. Drop your email — you&rsquo;ll join the waitlist and we&rsquo;ll get in touch when access expands.
              </>
            ) : (
              <>
                Aletheia is opening early access. <strong className="text-white">{seatsTaken} of {ALPHA_CAP} seats</strong> taken — <span className="text-white/95">{ALPHA_CAP - seatsTaken} left</span>. Drop your email and you&rsquo;re in.
              </>
            )}
          </p>

          <div className="p-6 rounded-2xl bg-white/10 border border-white/20 backdrop-blur-md max-w-2xl mx-auto">
            <form onSubmit={handleSubmit} className="flex flex-col sm:flex-row items-center gap-3">
              <Input
                id="email-input"
                name="email"
                type="email"
                placeholder="your@email.com"
                required
                className="flex-1 w-full bg-white/10 border-white/20 text-white placeholder:text-white/60 focus:border-white/40 rounded-full px-5 h-14 text-base"
              />
              <Button
                type="submit"
                size="lg"
                variant="secondary"
                disabled={isPending || cooldown > 0}
                className="w-full sm:w-auto h-14 bg-white text-blue-600 hover:bg-white/90 px-6 text-base rounded-full shadow-xl transition-all hover:scale-105 whitespace-nowrap font-bold disabled:opacity-50"
              >
                {isPending ? "Saving you a seat…" : cooldown > 0 ? `Wait ${cooldown}s` : "Request access"}
                {!isPending && cooldown <= 0 && <ArrowRight className="ml-2 w-4 h-4" />}
              </Button>
            </form>

            {(status.type || cooldown > 0) && (
              <div className={cn(
                "mt-4 p-3 rounded-xl text-sm font-medium animate-in fade-in slide-in-from-top-2",
                status.type === 'success' ? "bg-green-500/20 text-green-200 border border-green-500/30" :
                  "bg-red-500/20 text-red-200 border border-red-500/30"
              )}>
                {status.type === 'success' ? status.message :
                  cooldown > 0 ? `Hold up — wait ${cooldown}s and try again.` : status.message}
              </div>
            )}
          </div>

          <p className="mt-6 text-sm text-white/60">
            No credit card. We&rsquo;ll only use your email to send your sign-in details and rare product updates.{" "}
            <a href="/privacy" className="underline hover:text-white/80 transition">Privacy policy</a>.
          </p>
        </div>
      </div>
    </section>
  );
}


// Main Component
export default function TripGenieLanding() {
  return (
    <PageWrapper>
      <HeroSection />
      <ProofSection />
      <FeaturesSection />
      <CTASection />
    </PageWrapper>
  );
}
