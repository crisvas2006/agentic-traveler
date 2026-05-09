"use client";

import * as React from "react";
import { useEffect, useRef, useState } from "react";
import { cn } from "@/lib/utils";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Sparkles, Compass, Zap, Shield, Mail, ArrowRight, MapPin, Calendar, Users, Star } from "lucide-react";

import { useInView } from "@/hooks/use-in-view";
import { PageWrapper } from "@/components/layout/PageWrapper";

// Hero Section Component
function HeroSection() {
  const heroRef = useRef<HTMLElement>(null);
  const isInView = useInView(heroRef);

  return (
    <section
      ref={heroRef}
      className="relative min-h-[calc(100vh-64px)] flex items-center justify-center overflow-hidden"
    >

      <div className="container mx-auto px-4 relative z-10">
        <div
          className={cn(
            "max-w-4xl mx-auto text-center transition-all duration-1000",
            isInView ? "opacity-100 translate-y-0" : "opacity-0 translate-y-10"
          )}
        >
          <div className="inline-flex items-center gap-2 px-3 py-1 rounded-full bg-primary/10 border border-primary/20 backdrop-blur-sm mb-8">
            <Sparkles className="w-3.5 h-3.5 text-primary" />
            <span className="text-xs font-semibold text-primary uppercase tracking-wider">Alpha Access Available</span>
          </div>

          <h1 className="text-5xl md:text-7xl font-extrabold tracking-tight mb-6 leading-tight">
            <span className="bg-gradient-to-r from-blue-600 to-purple-600 bg-clip-text text-transparent animate-gradient-x bg-[length:200%_auto]">
              Travel planning made smart.<br />
              For the Individual,
            </span>
            <br />
            <span className="text-slate-800/90">
              Not the Average.
            </span>
          </h1>

          <p className="text-lg md:text-xl text-muted-foreground mb-12 max-w-3xl mx-auto leading-relaxed">
            Most platforms solve for the cheapest flight or the trendiest hotel. Trip Genie solves for the person. An AI travel companion that understands your energy levels, motivations, and life phases to create meaningful journeys.
          </p>

          <div className="flex flex-col sm:flex-row gap-4 justify-center items-center">
            <Button
              size="lg"
              className="text-lg px-8 h-14 rounded-full shadow-lg shadow-primary/25 hover:shadow-primary/40 transition-all hover:scale-105"
              onClick={() => {
                const emailInput = document.getElementById('email-input');
                if (emailInput) {
                  emailInput.scrollIntoView({ behavior: 'smooth', block: 'center' });
                  setTimeout(() => emailInput.focus(), 500);
                }
              }}
            >
              Start Planning
              <ArrowRight className="ml-2 w-5 h-5" />
            </Button>
            <Button
              size="lg"
              variant="outline"
              className="text-lg px-8 h-14 rounded-full border-border hover:bg-muted/50"
              onClick={() => {
                document.getElementById('proof-section')?.scrollIntoView({ behavior: 'smooth', block: 'start' });
              }}
            >
              Learn More
            </Button>
          </div>
        </div>
      </div>

      {/* Scroll Indicator */}
      <div className="absolute bottom-8 left-1/2 -translate-x-1/2 animate-bounce">
        <div className="w-6 h-10 border-2 border-purple-400/50 rounded-full flex justify-center">
          <div className="w-1 h-3 bg-purple-400 rounded-full mt-2 animate-pulse" />
        </div>
      </div>
    </section>
  );
}

// Proof Section Component
function ProofSection() {
  const sectionRef = useRef<HTMLElement>(null);
  const isInView = useInView(sectionRef);

  const roadmap = [
    {
      phase: "Current Alpha",
      title: "Discovery & Planning",
      description: "Core AI planning and personalized destination discovery with realtime events and weather data.",
      active: true
    },
    {
      phase: "Upcoming",
      title: "Interactive Itineraries",
      description: "Trip structure with multiple layers and map.",
      active: false
    },
    {
      phase: "Future Vision",
      title: "Seamless & Social",
      description: "Group trips, automated bookings, social matching.",
      active: false
    },
  ];

  return (
    <section id="proof-section" ref={sectionRef} className="py-24 relative overflow-hidden">
      <div className="absolute inset-0 bg-[radial-gradient(circle_at_center,rgba(59,130,246,0.05)_0%,transparent_70%)]" />

      <div className="container mx-auto px-4 relative z-10">
        <div
          className={cn(
            "text-center mb-16 transition-all duration-1000 delay-200",
            isInView ? "opacity-100 translate-y-0" : "opacity-0 translate-y-10"
          )}
        >
          <h2 className="text-4xl md:text-5xl font-bold tracking-tight mb-6">
            Everything You Need for the
            <br />
            <span className="bg-gradient-to-r from-blue-600 to-purple-600 bg-clip-text text-transparent">Perfect Trip</span>
          </h2>
          <p className="text-lg text-muted-foreground max-w-2xl mx-auto">
            Powered by AI and designed for travelers who want more from their journeys.
          </p>
        </div>

        <div className="grid md:grid-cols-3 gap-8 max-w-5xl mx-auto">
          {roadmap.map((item, index) => (
            <div
              key={index}
              className={cn(
                "relative p-8 rounded-2xl border backdrop-blur-sm transition-all duration-1000 hover:scale-105",
                item.active
                  ? "bg-primary/10 border-primary/30 shadow-lg shadow-primary/5"
                  : "bg-muted border-border hover:bg-background hover:border-primary/20",
                isInView ? "opacity-100 translate-y-0" : "opacity-0 translate-y-10"
              )}
              style={{ transitionDelay: `${index * 150 + 400}ms` }}
            >
              {item.active && (
                <div className="absolute -top-3 -right-3">
                  <span className="relative flex h-6 w-6">
                    <span className="animate-ping absolute inline-flex h-full w-full rounded-full bg-primary/40 opacity-75"></span>
                    <span className="relative inline-flex rounded-full h-6 w-6 bg-primary items-center justify-center">
                      <Sparkles className="w-3 h-3 text-white" />
                    </span>
                  </span>
                </div>
              )}
              <div className={cn(
                "text-sm font-semibold mb-2 uppercase tracking-wider",
                item.active ? "text-primary" : "text-muted-foreground"
              )}>
                {item.phase}
              </div>
              <h3 className="text-2xl font-bold text-foreground mb-4">{item.title}</h3>
              <p className="text-muted-foreground leading-relaxed">{item.description}</p>
            </div>
          ))}
        </div>
      </div>
    </section>
  );
}

// Features Section Component
function FeaturesSection() {
  const sectionRef = useRef<HTMLElement>(null);
  const isInView = useInView(sectionRef);

  const features = [
    {
      icon: Compass,
      title: "Intuitive Discovery",
      description: "Input vague requests like 'five days in late spring, feeling tired, want nature and culture' and receive curated destinations that fit your profile.",
      color: "from-purple-500 to-violet-500",
    },
    {
      icon: Calendar,
      title: "Flexible Itineraries",
      description: "Move away from rigid schedules with day-level plans that offer alternatives for different energy levels and moods.",
      color: "from-violet-500 to-purple-500",
    },
    {
      icon: Zap,
      title: "Live Adaptation",
      description: "During your trip, share your current mood or weather changes via Telegram, and get actionable suggestions to improve your day.",
      color: "from-purple-600 to-violet-600",
    },
    {
      icon: Shield,
      title: "Traveler DNA",
      description: "The Odyssey Onboarding creates your structured Traveler DNA, filtering every suggestion through your personal lens of preferences and needs.",
      color: "from-violet-600 to-purple-600",
    },
  ];

  return (
    <section ref={sectionRef} className="py-24 relative overflow-hidden">
      <div className="absolute inset-0">
        <div className="absolute top-0 left-1/4 w-96 h-96 bg-primary/5 rounded-full blur-[120px]" />
        <div className="absolute bottom-0 right-1/4 w-96 h-96 bg-purple-600/5 rounded-full blur-[120px]" />
      </div>

      <div className="container mx-auto px-4 relative z-10">
        <div
          className={cn(
            "text-center mb-16 transition-all duration-1000",
            isInView ? "opacity-100 translate-y-0" : "opacity-0 translate-y-10"
          )}
        >
          <h2 className="text-4xl md:text-5xl font-bold mb-6 tracking-tight">
            How the Companion Works
          </h2>
          <p className="text-lg text-muted-foreground max-w-2xl mx-auto">
            A different approach to travel planning that adapts to you, not the other way around.
          </p>
        </div>

        <div className="grid md:grid-cols-2 gap-8 max-w-6xl mx-auto">
          {features.map((feature, index) => {
            const Icon = feature.icon;
            return (
              <div
                key={index}
                className={cn(
                  "group p-8 rounded-2xl bg-muted/50 border border-border backdrop-blur-sm transition-all duration-1000 hover:bg-background hover:border-primary/30 hover:scale-105 hover:shadow-xl hover:shadow-primary/5",
                  isInView ? "opacity-100 translate-y-0" : "opacity-0 translate-y-10"
                )}
                style={{ transitionDelay: `${index * 150}ms` }}
              >
                <div className={cn("w-14 h-14 rounded-2xl bg-gradient-to-br flex items-center justify-center mb-6 group-hover:scale-110 transition-transform", feature.color)}>
                  <Icon className="w-7 h-7 text-white" />
                </div>
                <h3 className="text-2xl font-bold text-foreground mb-4">{feature.title}</h3>
                <p className="text-muted-foreground leading-relaxed">{feature.description}</p>
              </div>
            );
          })}
        </div>

        {/* Problem Statement */}
        <div
          className={cn(
            "mt-20 max-w-4xl mx-auto p-8 rounded-2xl bg-primary/5 border border-primary/10 backdrop-blur-sm transition-all duration-1000",
            isInView ? "opacity-100 translate-y-0" : "opacity-0 translate-y-10"
          )}
          style={{ transitionDelay: "600ms" }}
        >
          <h3 className="text-2xl font-bold text-foreground mb-4">The Problem with Static Planning</h3>
          <p className="text-muted-foreground leading-relaxed">
            Hours are spent bouncing between blogs and booking sites with fuzzy desires but no clear destination. The result is often a trip chosen for the price rather than the fit, leading to overcrowded itineraries that fail to adapt when the weather turns or energy fades.
          </p>
        </div>
      </div>
    </section>
  );
}

// CTA Section Component
function CTASection() {
  const sectionRef = useRef<HTMLElement>(null);
  const isInView = useInView(sectionRef);
  const [email, setEmail] = useState("");

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    console.log("Email submitted:", email);
    setEmail("");
  };

  return (
    <section ref={sectionRef} className="pt-40 pb-32 bg-gradient-to-br from-blue-600 to-purple-600 text-white relative overflow-hidden">
      <div className="absolute inset-0">
        <div className="absolute top-1/2 left-1/2 -translate-x-1/2 -translate-y-1/2 w-[800px] h-[800px] bg-white/10 rounded-full blur-[150px] animate-pulse" />
      </div>

      <div className="container mx-auto px-4 relative z-10">
        <div
          className={cn(
            "max-w-3xl mx-auto text-center transition-all duration-1000",
            isInView ? "opacity-100 translate-y-0" : "opacity-0 translate-y-10"
          )}
        >
          <h2 className="text-4xl md:text-5xl font-bold tracking-tight mb-6">
            Ready to Transform Your Travel Experience?
          </h2>

          <p className="text-lg text-white/90 mb-12 leading-relaxed">
            Join other travelers who are already planning smarter with our AI-powered platform. Limited alpha access is now open for early adopters.
          </p>

          <div className="p-8 rounded-2xl bg-white/10 border border-white/20 backdrop-blur-md max-w-2xl mx-auto">
            <form onSubmit={handleSubmit} className="flex flex-col sm:flex-row items-center gap-4">
              <Input
                id="email-input"
                type="email"
                placeholder="Enter your email"
                value={email}
                onChange={(e) => setEmail(e.target.value)}
                required
                className="flex-1 w-full bg-white/10 border-white/20 text-white placeholder:text-white/60 focus:border-white/40 rounded-full px-6 h-16 text-lg"
              />
              <Button
                type="submit"
                size="lg"
                variant="secondary"
                className="w-full sm:w-auto h-16 bg-white text-blue-600 hover:bg-white/90 px-8 text-lg rounded-full shadow-xl transition-all hover:scale-105 whitespace-nowrap font-bold"
              >
                Get Started
                <ArrowRight className="ml-2 w-5 h-5" />
              </Button>
            </form>
          </div>

          <p className="mt-6 text-sm text-white/60">
            We respect your privacy. No credit card required for alpha entry.
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
