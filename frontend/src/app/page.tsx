"use client";

import * as React from "react";
import { useEffect, useRef, useState } from "react";
import { cn } from "@/lib/utils";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Sparkles, Compass, Zap, Shield, Mail, ArrowRight, MapPin, Calendar, Users, Star } from "lucide-react";

// Utility function for animations
const useInView = (ref: React.RefObject<HTMLElement | null>, threshold = 0.1) => {
  const [isInView, setIsInView] = useState(false);

  useEffect(() => {
    const observer = new IntersectionObserver(
      ([entry]) => {
        if (entry.isIntersecting) {
          setIsInView(true);
        }
      },
      { threshold }
    );

    if (ref.current) {
      observer.observe(ref.current);
    }

    return () => {
      if (ref.current) {
        observer.unobserve(ref.current);
      }
    };
  }, [ref, threshold]);

  return isInView;
};

// Hero Section Component
function HeroSection() {
  const heroRef = useRef<HTMLElement>(null);
  const isInView = useInView(heroRef);

  return (
    <section
      ref={heroRef}
      className="relative min-h-screen flex items-center justify-center overflow-hidden bg-gradient-to-b from-[#0a0118] via-[#1a0a2e] to-[#0a0118]"
    >
      {/* Cosmic Background */}
      <div className="absolute inset-0 overflow-hidden">
        <div className="absolute top-1/4 left-1/4 w-96 h-96 bg-purple-600/20 rounded-full blur-[120px] animate-pulse" />
        <div className="absolute bottom-1/4 right-1/4 w-96 h-96 bg-violet-600/20 rounded-full blur-[120px] animate-pulse delay-1000" />
        <div className="absolute top-1/2 left-1/2 -translate-x-1/2 -translate-y-1/2 w-[600px] h-[600px] bg-purple-500/10 rounded-full blur-[150px]" />

        {/* Stars */}
        {[...Array(50)].map((_, i) => (
          <div
            key={i}
            className="absolute w-1 h-1 bg-white rounded-full animate-pulse"
            style={{
              top: `${Math.random() * 100}%`,
              left: `${Math.random() * 100}%`,
              animationDelay: `${Math.random() * 3}s`,
              opacity: Math.random() * 0.7 + 0.3,
            }}
          />
        ))}
      </div>

      <div className="container mx-auto px-4 relative z-10">
        <div
          className={cn(
            "max-w-4xl mx-auto text-center transition-all duration-1000",
            isInView ? "opacity-100 translate-y-0" : "opacity-0 translate-y-10"
          )}
        >
          <div className="inline-flex items-center gap-2 px-4 py-2 rounded-full bg-purple-500/10 border border-purple-500/20 backdrop-blur-sm mb-8">
            <Sparkles className="w-4 h-4 text-purple-400" />
            <span className="text-sm text-purple-300">Alpha Access Available</span>
          </div>

          <h1 className="text-5xl md:text-7xl font-bold mb-6 bg-gradient-to-r from-purple-200 via-violet-200 to-purple-200 bg-clip-text text-transparent leading-tight">
            Travel for the Individual,
            <br />
            Not the Average.
          </h1>

          <p className="text-lg md:text-xl text-purple-200/80 mb-12 max-w-3xl mx-auto leading-relaxed">
            Most platforms solve for the cheapest flight or the trendiest hotel. Agentic Traveler solves for the person. An AI travel companion that understands your energy levels, motivations, and life phases to create meaningful journeys.
          </p>

          <div className="flex flex-col sm:flex-row gap-4 justify-center items-center">
            <Button
              size="lg"
              className="bg-gradient-to-r from-purple-600 to-violet-600 hover:from-purple-700 hover:to-violet-700 text-white px-8 py-6 text-lg rounded-full shadow-lg shadow-purple-500/30 transition-all hover:shadow-purple-500/50 hover:scale-105"
            >
              Request Alpha Access
              <ArrowRight className="ml-2 w-5 h-5" />
            </Button>
            <Button
              size="lg"
              variant="outline"
              className="border-purple-500/30 text-purple-200 hover:bg-purple-500/10 px-8 py-6 text-lg rounded-full backdrop-blur-sm"
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

  const stats = [
    { value: "1+", label: "Early Adopters" },
    { value: "150+", label: "Destinations" },
    { value: "97%", label: "Satisfaction" },
    { value: "24/7", label: "AI Support" },
  ];

  return (
    <section ref={sectionRef} className="py-24 bg-gradient-to-b from-[#0a0118] to-[#1a0a2e] relative overflow-hidden">
      <div className="absolute inset-0 bg-[radial-gradient(circle_at_center,rgba(139,92,246,0.1)_0%,transparent_70%)]" />

      <div className="container mx-auto px-4 relative z-10">
        <div
          className={cn(
            "text-center mb-16 transition-all duration-1000 delay-200",
            isInView ? "opacity-100 translate-y-0" : "opacity-0 translate-y-10"
          )}
        >
          <h2 className="text-4xl md:text-5xl font-bold mb-6 bg-gradient-to-r from-purple-200 to-violet-200 bg-clip-text text-transparent">
            Trusted by Travelers Worldwide
          </h2>
          <p className="text-lg text-purple-200/70 max-w-2xl mx-auto">
            Join thousands who have transformed their travel experience with personalized AI guidance
          </p>
        </div>

        <div className="grid grid-cols-2 md:grid-cols-4 gap-8 max-w-5xl mx-auto">
          {stats.map((stat, index) => (
            <div
              key={index}
              className={cn(
                "text-center p-6 rounded-2xl bg-purple-500/5 border border-purple-500/10 backdrop-blur-sm transition-all duration-1000 hover:bg-purple-500/10 hover:border-purple-500/20",
                isInView ? "opacity-100 translate-y-0" : "opacity-0 translate-y-10"
              )}
              style={{ transitionDelay: `${index * 100 + 400}ms` }}
            >
              <div className="text-4xl md:text-5xl font-bold bg-gradient-to-r from-purple-400 to-violet-400 bg-clip-text text-transparent mb-2">
                {stat.value}
              </div>
              <div className="text-purple-200/60 text-sm">{stat.label}</div>
            </div>
          ))}
        </div>

        {/* Testimonial Cards */}
        <div className="mt-20 grid md:grid-cols-3 gap-6 max-w-6xl mx-auto">
          {[
            {
              name: "Sarah Chen",
              role: "Digital Nomad",
              content: "Finally, a travel app that understands I need downtime between adventures. The AI actually gets me.",
              rating: 5,
            },
            {
              name: "Marcus Rodriguez",
              role: "Adventure Seeker",
              content: "The app suggested destinations I never would have considered, and they were perfect.",
              rating: 5,
            },
            {
              name: "Emma Thompson",
              role: "Solo Traveler",
              content: "Real-time adaptation saved my trip when weather turned bad. The AI suggested alternatives that made the day even better.",
              rating: 5,
            },
          ].map((testimonial, index) => (
            <div
              key={index}
              className={cn(
                "p-6 rounded-2xl bg-purple-500/5 border border-purple-500/10 backdrop-blur-sm transition-all duration-1000 hover:bg-purple-500/10",
                isInView ? "opacity-100 translate-y-0" : "opacity-0 translate-y-10"
              )}
              style={{ transitionDelay: `${index * 150 + 600}ms` }}
            >
              <div className="flex gap-1 mb-4">
                {[...Array(testimonial.rating)].map((_, i) => (
                  <Star key={i} className="w-4 h-4 fill-purple-400 text-purple-400" />
                ))}
              </div>
              <p className="text-purple-200/80 mb-4 italic">"{testimonial.content}"</p>
              <div>
                <div className="font-semibold text-purple-200">{testimonial.name}</div>
                <div className="text-sm text-purple-200/60">{testimonial.role}</div>
              </div>
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
    <section ref={sectionRef} className="py-24 bg-gradient-to-b from-[#1a0a2e] to-[#0a0118] relative overflow-hidden">
      <div className="absolute inset-0">
        <div className="absolute top-0 left-1/4 w-96 h-96 bg-purple-600/10 rounded-full blur-[120px]" />
        <div className="absolute bottom-0 right-1/4 w-96 h-96 bg-violet-600/10 rounded-full blur-[120px]" />
      </div>

      <div className="container mx-auto px-4 relative z-10">
        <div
          className={cn(
            "text-center mb-16 transition-all duration-1000",
            isInView ? "opacity-100 translate-y-0" : "opacity-0 translate-y-10"
          )}
        >
          <h2 className="text-4xl md:text-5xl font-bold mb-6 bg-gradient-to-r from-purple-200 to-violet-200 bg-clip-text text-transparent">
            How the Companion Works
          </h2>
          <p className="text-lg text-purple-200/70 max-w-2xl mx-auto">
            A different approach to travel planning that adapts to you, not the other way around
          </p>
        </div>

        <div className="grid md:grid-cols-2 gap-8 max-w-6xl mx-auto">
          {features.map((feature, index) => {
            const Icon = feature.icon;
            return (
              <div
                key={index}
                className={cn(
                  "group p-8 rounded-2xl bg-purple-500/5 border border-purple-500/10 backdrop-blur-sm transition-all duration-1000 hover:bg-purple-500/10 hover:border-purple-500/20 hover:scale-105",
                  isInView ? "opacity-100 translate-y-0" : "opacity-0 translate-y-10"
                )}
                style={{ transitionDelay: `${index * 150}ms` }}
              >
                <div className={cn("w-14 h-14 rounded-2xl bg-gradient-to-br flex items-center justify-center mb-6 group-hover:scale-110 transition-transform", feature.color)}>
                  <Icon className="w-7 h-7 text-white" />
                </div>
                <h3 className="text-2xl font-bold text-purple-200 mb-4">{feature.title}</h3>
                <p className="text-purple-200/70 leading-relaxed">{feature.description}</p>
              </div>
            );
          })}
        </div>

        {/* Problem Statement */}
        <div
          className={cn(
            "mt-20 max-w-4xl mx-auto p-8 rounded-2xl bg-gradient-to-br from-purple-500/10 to-violet-500/10 border border-purple-500/20 backdrop-blur-sm transition-all duration-1000",
            isInView ? "opacity-100 translate-y-0" : "opacity-0 translate-y-10"
          )}
          style={{ transitionDelay: "600ms" }}
        >
          <h3 className="text-2xl font-bold text-purple-200 mb-4">The Problem with Static Planning</h3>
          <p className="text-purple-200/80 leading-relaxed">
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
    <section ref={sectionRef} className="py-24 bg-gradient-to-b from-[#0a0118] to-[#1a0a2e] relative overflow-hidden">
      <div className="absolute inset-0">
        <div className="absolute top-1/2 left-1/2 -translate-x-1/2 -translate-y-1/2 w-[800px] h-[800px] bg-purple-500/10 rounded-full blur-[150px]" />
      </div>

      <div className="container mx-auto px-4 relative z-10">
        <div
          className={cn(
            "max-w-3xl mx-auto text-center transition-all duration-1000",
            isInView ? "opacity-100 translate-y-0" : "opacity-0 translate-y-10"
          )}
        >
          <div className="inline-flex items-center gap-2 px-4 py-2 rounded-full bg-purple-500/10 border border-purple-500/20 backdrop-blur-sm mb-8">
            <Shield className="w-4 h-4 text-purple-400" />
            <span className="text-sm text-purple-300">Limited Alpha Access</span>
          </div>

          <h2 className="text-4xl md:text-5xl font-bold mb-6 bg-gradient-to-r from-purple-200 to-violet-200 bg-clip-text text-transparent">
            Ready to travel with intention?
          </h2>

          <p className="text-lg text-purple-200/80 mb-12 leading-relaxed">
            Agentic Traveler is currently in a closed alpha phase. Access is being granted in small waves to ensure the coordination of specialized agents remains precise and deeply personalized for every traveler.
          </p>

          <div className="p-8 rounded-2xl bg-gradient-to-br from-purple-500/10 to-violet-500/10 border border-purple-500/20 backdrop-blur-sm">
            <form onSubmit={handleSubmit} className="flex flex-col sm:flex-row gap-4">
              <Input
                type="email"
                placeholder="Enter your email"
                value={email}
                onChange={(e) => setEmail(e.target.value)}
                required
                className="flex-1 bg-purple-500/5 border-purple-500/20 text-purple-200 placeholder:text-purple-200/40 focus:border-purple-500/40 rounded-full px-6 py-6 text-lg"
              />
              <Button
                type="submit"
                size="lg"
                className="bg-gradient-to-r from-purple-600 to-violet-600 hover:from-purple-700 hover:to-violet-700 text-white px-8 py-6 text-lg rounded-full shadow-lg shadow-purple-500/30 transition-all hover:shadow-purple-500/50 hover:scale-105 whitespace-nowrap"
              >
                Yes, I want in!
                <Mail className="ml-2 w-5 h-5" />
              </Button>
            </form>
          </div>

          <p className="mt-6 text-sm text-purple-200/60">
            We respect your privacy. Your email will only be used for alpha access notifications.
          </p>
        </div>
      </div>
    </section>
  );
}

// Footer Component
function Footer() {
  return (
    <footer className="py-12 bg-[#0a0118] border-t border-purple-500/10">
      <div className="container mx-auto px-4">
        <div className="grid md:grid-cols-4 gap-8 mb-8">
          <div>
            <h3 className="text-xl font-bold bg-gradient-to-r from-purple-400 to-violet-400 bg-clip-text text-transparent mb-4">
              Agentic Traveler
            </h3>
            <p className="text-purple-200/60 text-sm">
              Travel for the individual, not the average.
            </p>
          </div>

          <div>
            <h4 className="text-purple-200 font-semibold mb-4">Product</h4>
            <ul className="space-y-2 text-sm text-purple-200/60">
              <li><a href="#" className="hover:text-purple-400 transition-colors">Features</a></li>
              <li><a href="#" className="hover:text-purple-400 transition-colors">How it Works</a></li>
              <li><a href="#" className="hover:text-purple-400 transition-colors">Pricing</a></li>
              <li><a href="#" className="hover:text-purple-400 transition-colors">FAQ</a></li>
            </ul>
          </div>

          <div>
            <h4 className="text-purple-200 font-semibold mb-4">Company</h4>
            <ul className="space-y-2 text-sm text-purple-200/60">
              <li><a href="#" className="hover:text-purple-400 transition-colors">About</a></li>
              <li><a href="#" className="hover:text-purple-400 transition-colors">Blog</a></li>
              <li><a href="#" className="hover:text-purple-400 transition-colors">Contact</a></li>
            </ul>
          </div>

          <div>
            <h4 className="text-purple-200 font-semibold mb-4">Legal</h4>
            <ul className="space-y-2 text-sm text-purple-200/60">
              <li><a href="#" className="hover:text-purple-400 transition-colors">Privacy Policy</a></li>
              <li><a href="#" className="hover:text-purple-400 transition-colors">Terms of Service</a></li>
              <li><a href="#" className="hover:text-purple-400 transition-colors">Cookie Policy</a></li>
            </ul>
          </div>
        </div>

        <div className="pt-8 border-t border-purple-500/10 flex flex-col sm:flex-row justify-between items-center gap-4">
          <p className="text-purple-200/60 text-sm">
            © 2026 Agentic Traveler. All rights reserved.
          </p>
          <div className="flex gap-4">
            <a href="#" className="text-purple-200/60 hover:text-purple-400 transition-colors">
              <Users className="w-5 h-5" />
            </a>
            <a href="#" className="text-purple-200/60 hover:text-purple-400 transition-colors">
              <MapPin className="w-5 h-5" />
            </a>
            <a href="#" className="text-purple-200/60 hover:text-purple-400 transition-colors">
              <Mail className="w-5 h-5" />
            </a>
          </div>
        </div>
      </div>
    </footer>
  );
}

// Main Component
export default function AgenticTravelerLanding() {
  return (
    <div className="min-h-screen bg-[#0a0118] text-white">
      <HeroSection />
      <ProofSection />
      <FeaturesSection />
      <CTASection />
      <Footer />
    </div>
  );
}
