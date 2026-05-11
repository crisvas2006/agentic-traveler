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
      <section ref={headerRef} className="py-20 relative overflow-hidden">
        <div className="container mx-auto px-4 relative z-10">
          <div className={cn(
            "max-w-4xl mx-auto text-center transition-all duration-1000",
            isInView ? "opacity-100 translate-y-0" : "opacity-0 translate-y-10"
          )}>
            <h1 className="text-4xl md:text-5xl font-bold mb-4 tracking-tight">
              Simple, Credit-Based Access
            </h1>
            <p className="text-lg text-muted-foreground leading-relaxed mb-12">
              During our alpha phase, we use a fair credit system to ensure every traveler gets the processing power they need.
            </p>

            <div className="max-w-md mx-auto p-1px bg-gradient-to-b from-primary to-purple-600 rounded-[2rem]">
              <div className="bg-background rounded-[1.9rem] p-6 md:p-10 text-left relative overflow-hidden border border-border">
                <div className="absolute top-0 right-0 p-6 opacity-5">
                  <Sparkles className="w-20 h-20 text-primary" />
                </div>
                
                <div className="inline-flex items-center gap-2 px-3 py-1 rounded-full bg-primary/10 border border-primary/20 mb-6">
                  <Zap className="w-3.5 h-3.5 text-primary" />
                  <span className="text-xs font-bold text-primary uppercase tracking-wider">Alpha Special</span>
                </div>

                <div className="mb-6">
                  <span className="text-4xl font-bold text-foreground">$0</span>
                  <span className="text-sm text-muted-foreground ml-2">/ during alpha</span>
                </div>

                <ul className="space-y-3.5 mb-8">
                  {[
                    "Free initial credit allowance",
                    "Enough for 1 complete trip plan",
                    "Access to all specialized agents",
                    "Telegram companion access",
                    "Personalized Traveler DNA",
                  ].map((feature, i) => (
                    <li key={i} className="flex items-center gap-3 text-sm text-muted-foreground">
                      <div className="w-4.5 h-4.5 rounded-full bg-primary/10 flex items-center justify-center shrink-0">
                        <Check className="w-2.5 h-2.5 text-primary" />
                      </div>
                      {feature}
                    </li>
                  ))}
                </ul>

                <Button className="w-full h-12 rounded-full text-base font-bold shadow-lg shadow-primary/20 hover:shadow-primary/30 transition-all hover:scale-[1.02]" asChild>
                  <Link href="/#email-input">Get Started for Free</Link>
                </Button>
                
                <p className="text-center mt-5 text-xs text-muted-foreground">
                  No credit card required for alpha entry.
                </p>
              </div>
            </div>

            <div className="mt-12 text-left max-w-2xl mx-auto p-6 rounded-2xl bg-muted border border-border">
              <h3 className="text-lg font-bold text-foreground mb-3">How credits work:</h3>
              <p className="text-sm text-muted-foreground leading-relaxed">
                Credits are deducted for each major interaction with the agents (Discovery, Planning, and active Companion mode). This helps us manage API costs while providing you with high-quality, personalized reasoning. New alpha users receive enough credits to fully plan their first major journey.
              </p>
            </div>
          </div>
        </div>
      </section>
    </PageWrapper>
  );
}
