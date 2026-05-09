"use client";

import { PageWrapper } from "@/components/layout/PageWrapper";
import { Zap, Check, Sparkles } from "lucide-react";
import { cn } from "@/lib/utils";
import { useRef } from "react";
import { useInView } from "@/hooks/use-in-view";
import { Button } from "@/components/ui/button";
import Link from "next/link";

export default function PricingPage() {
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
              Simple, Credit-Based Access
            </h1>
            <p className="text-xl text-muted-foreground leading-relaxed mb-16">
              During our alpha phase, we use a fair credit system to ensure every traveler gets the processing power they need.
            </p>

            <div className="max-w-md mx-auto p-1px bg-gradient-to-b from-primary to-purple-600 rounded-[2.5rem]">
              <div className="bg-background rounded-[2.4rem] p-8 md:p-12 text-left relative overflow-hidden border border-border">
                <div className="absolute top-0 right-0 p-6 opacity-5">
                  <Sparkles className="w-24 h-24 text-primary" />
                </div>
                
                <div className="inline-flex items-center gap-2 px-3 py-1 rounded-full bg-primary/10 border border-primary/20 mb-6">
                  <Zap className="w-4 h-4 text-primary" />
                  <span className="text-xs font-bold text-primary uppercase tracking-wider">Alpha Special</span>
                </div>

                <div className="mb-8">
                  <span className="text-5xl font-bold text-foreground">$0</span>
                  <span className="text-muted-foreground ml-2">/ during alpha</span>
                </div>

                <ul className="space-y-4 mb-10">
                  {[
                    "Free initial credit allowance",
                    "Enough for 1 complete trip plan",
                    "Access to all specialized agents",
                    "Telegram companion access",
                    "Personalized Traveler DNA",
                  ].map((feature, i) => (
                    <li key={i} className="flex items-center gap-3 text-muted-foreground">
                      <div className="w-5 h-5 rounded-full bg-primary/10 flex items-center justify-center shrink-0">
                        <Check className="w-3 h-3 text-primary" />
                      </div>
                      {feature}
                    </li>
                  ))}
                </ul>

                <Button className="w-full h-14 rounded-full text-lg font-bold shadow-lg shadow-primary/20 hover:shadow-primary/30 transition-all hover:scale-[1.02]" asChild>
                  <Link href="/#email-input">Get Started for Free</Link>
                </Button>
                
                <p className="text-center mt-6 text-sm text-muted-foreground">
                  No credit card required for alpha entry.
                </p>
              </div>
            </div>

            <div className="mt-16 text-left max-w-2xl mx-auto p-8 rounded-2xl bg-muted border border-border">
              <h3 className="text-xl font-bold text-foreground mb-4">How credits work:</h3>
              <p className="text-muted-foreground leading-relaxed">
                Credits are deducted for each major interaction with the agents (Discovery, Planning, and active Companion mode). This helps us manage API costs while providing you with high-quality, personalized reasoning. New alpha users receive enough credits to fully plan their first major journey.
              </p>
            </div>
          </div>
        </div>
      </section>
    </PageWrapper>
  );
}
