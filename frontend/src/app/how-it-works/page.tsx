"use client";

import { PageWrapper } from "@/components/layout/PageWrapper";
import { ListChecks, Brain, MessageSquare, ArrowRight, Smartphone, Globe } from "lucide-react";
import { cn } from "@/lib/utils";
import { useRef } from "react";
import { useInView } from "@/hooks/use-in-view";

const steps = [
  {
    icon: ListChecks,
    title: "The Odyssey Onboarding",
    description: "Start with our deep-dive questionnaire. We ask about your energy levels, risk tolerance, and past travel experiences to build a foundation.",
  },
  {
    icon: Brain,
    title: "Traveler DNA Mapping",
    description: "Our agents process your responses to create a 'Traveler DNA'—a structured profile that guides every suggestion we ever make for you.",
  },
  {
    icon: MessageSquare,
    title: "Chat via Telegram",
    description: "Currently, you interact with Aletheia Travel via our Telegram bot. It's fast, mobile-first, and always ready to help.",
  },
];

export default function HowItWorksPage() {
  const headerRef = useRef<HTMLElement>(null);
  const isInView = useInView(headerRef);

  return (
    <PageWrapper>
      <section ref={headerRef} className="py-20 relative overflow-hidden">
        <div className="container mx-auto px-4 relative z-10">
          <div className={cn(
            "max-w-4xl mx-auto transition-all duration-1000",
            isInView ? "opacity-100 translate-y-0" : "opacity-0 translate-y-10"
          )}>
            <div className="text-center mb-16">
              <h1 className="text-4xl md:text-5xl font-bold mb-4 tracking-tight">
                How it Works
              </h1>
              <p className="text-lg text-muted-foreground leading-relaxed max-w-2xl mx-auto">
                From deep personalization to real-time companionship, here is how we transform your travel experience.
              </p>
            </div>

            <div className="space-y-8">
              {steps.map((step, index) => {
                const Icon = step.icon;
                return (
                  <div key={index} className="flex gap-6 items-start p-6 rounded-2xl bg-muted border border-border backdrop-blur-sm transition-all hover:border-primary/30">
                    <div className="w-14 h-14 rounded-xl bg-primary/10 border border-primary/20 flex items-center justify-center shrink-0">
                      <Icon className="w-7 h-7 text-primary" />
                    </div>
                    <div>
                      <div className="flex items-center gap-3 mb-2">
                        <span className="text-primary font-bold text-sm">0{index + 1}</span>
                        <h3 className="text-xl font-bold text-foreground">{step.title}</h3>
                      </div>
                      <p className="text-base text-muted-foreground leading-relaxed">
                        {step.description}
                      </p>
                    </div>
                  </div>
                );
              })}
            </div>

            <div className="mt-16 p-6 rounded-3xl bg-primary/5 border border-primary/20 text-center">
              <h2 className="text-2xl font-bold text-foreground mb-3 flex items-center justify-center gap-3">
                <Globe className="w-7 h-7 text-primary" />
                Coming Soon: Web Interface
              </h2>
              <p className="text-muted-foreground text-base mb-0 leading-relaxed">
                While our Telegram bot is the heart of the alpha experience, we are currently building a full web interface. Soon, you'll be able to manage your Traveler DNA, explore itineraries, and chat with your companion directly from our site.
              </p>
            </div>
          </div>
        </div>
      </section>
    </PageWrapper>
  );
}
