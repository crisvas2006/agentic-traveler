"use client";

import { PageWrapper } from "@/components/layout/PageWrapper";
import { Compass, Zap, Shield, Sparkles, Map, Brain, MessageSquare, Lock } from "lucide-react";
import { cn } from "@/lib/utils";
import { useRef } from "react";
import { useInView } from "@/hooks/use-in-view";

const features = [
  {
    icon: Compass,
    title: "AI-Powered Discovery",
    description: "Tell us your mood, energy, and vague desires. We don't just find flights; we find the place that matches your current life phase.",
    color: "bg-purple-500",
  },
  {
    icon: Brain,
    title: "Traveler DNA",
    description: "The Odyssey Onboarding creates a deep, structured profile of your personality, risk tolerance, and motivations to filter every suggestion.",
    color: "bg-violet-500",
  },
  {
    icon: Zap,
    title: "Real-time Adaptation",
    description: "Weather turned bad? Energy fading? Tell the companion and get instant alternatives that save your day without the stress.",
    color: "bg-purple-600",
  },
  {
    icon: Map,
    title: "Flexible Itineraries",
    description: "Multi-layered plans that move away from rigid hourly schedules, offering options based on how you feel in the moment.",
    color: "bg-violet-600",
  },
  {
    icon: MessageSquare,
    title: "Telegram Integration",
    description: "Your travel companion lives in your pocket via Telegram, making it easy to share updates and get help on the go.",
    color: "bg-purple-500",
  },
  {
    icon: Lock,
    title: "Privacy First",
    description: "Your data is yours. We use it only to personalize your experience, with enterprise-grade security at every layer.",
  },
];

export default function FeaturesPage() {
  const headerRef = useRef<HTMLElement>(null);
  const isInView = useInView(headerRef);

  return (
    <PageWrapper>
      <section ref={headerRef} className="py-24 relative overflow-hidden">
        <div className="container mx-auto px-4 relative z-10">
          <div className={cn(
            "max-w-4xl mx-auto text-center transition-all duration-1000",
            isInView ? "opacity-100 translate-y-0" : "opacity-0 translate-y-10"
          )}>
            <h1 className="text-5xl md:text-6xl font-bold mb-6 tracking-tight">
              Built for the Individual
            </h1>
            <p className="text-xl text-muted-foreground leading-relaxed mb-16">
              Trip Genie isn't just another travel planner. It's an agentic system designed to understand you deeply and accompany you everywhere.
            </p>

            <div className="grid md:grid-cols-2 lg:grid-cols-3 gap-8 text-left">
              {features.map((feature, index) => {
                const Icon = feature.icon;
                return (
                  <div 
                    key={index}
                    className="p-8 rounded-2xl bg-muted border border-border backdrop-blur-sm hover:border-primary/30 transition-all group hover:bg-background"
                  >
                    <div className={cn("w-12 h-12 rounded-xl flex items-center justify-center mb-6 text-white group-hover:scale-110 transition-transform", feature.color || "bg-primary")}>
                      <Icon className="w-6 h-6" />
                    </div>
                    <h3 className="text-xl font-bold text-foreground mb-3">{feature.title}</h3>
                    <p className="text-muted-foreground leading-relaxed">
                      {feature.description}
                    </p>
                  </div>
                );
              })}
            </div>
          </div>
        </div>
      </section>
    </PageWrapper>
  );
}
