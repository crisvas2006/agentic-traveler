"use client";

import { PageWrapper } from "@/components/layout/PageWrapper";
import { Shield } from "lucide-react";
import { cn } from "../../lib/utils";
import { useRef } from "react";
import { useInView } from "@/hooks/use-in-view";

export default function PrivacyPage() {
  const headerRef = useRef<HTMLElement>(null);
  const isInView = useInView(headerRef);

  return (
    <PageWrapper>
      <section ref={headerRef} className="py-24 relative overflow-hidden">
        <div className="container mx-auto px-4 relative z-10">
          <div className={cn(
            "max-w-3xl mx-auto transition-all duration-1000",
            isInView ? "opacity-100 translate-y-0" : "opacity-0 translate-y-10"
          )}>
            <div className="flex items-center gap-4 mb-8">
              <Shield className="w-10 h-10 text-primary" />
              <h1 className="text-4xl md:text-5xl font-bold tracking-tight">
                Privacy Policy
              </h1>
            </div>

            <div className="space-y-12 text-muted-foreground leading-relaxed">
              <section>
                <h2 className="text-2xl font-bold text-foreground mb-4">1. Introduction</h2>
                <p>
                  At Trip Genie, we respect your privacy and are committed to protecting your personal data. This privacy policy will inform you as to how we look after your personal data when you visit our website or use our Telegram companion.
                </p>
              </section>

              <section>
                <h2 className="text-2xl font-bold text-foreground mb-4">2. The Data We Collect</h2>
                <p className="mb-4">
                  We may collect, use, store and transfer different kinds of personal data about you which we have grouped together as follows:
                </p>
                <ul className="space-y-4">
                  <li className="flex gap-3">
                    <span className="font-bold text-foreground shrink-0">• Identity Data:</span>
                    <span>includes first name, last name, username or similar identifier.</span>
                  </li>
                  <li className="flex gap-3">
                    <span className="font-bold text-foreground shrink-0">• Contact Data:</span>
                    <span>includes email address and Telegram ID.</span>
                  </li>
                  <li className="flex gap-3">
                    <span className="font-bold text-foreground shrink-0">• Traveler DNA Data:</span>
                    <span>includes your preferences, motivations, and trip styles collected through our onboarding process.</span>
                  </li>
                  <li className="flex gap-3">
                    <span className="font-bold text-foreground shrink-0">• Usage Data:</span>
                    <span>includes information about how you use our website, products and services.</span>
                  </li>
                </ul>
              </section>

              <section>
                <h2 className="text-2xl font-bold text-foreground mb-4">3. How We Use Your Data</h2>
                <p className="mb-4">
                  We will only use your personal data when the law allows us to. Most commonly, we will use your personal data in the following circumstances:
                </p>
                <ul className="space-y-3 pl-4">
                  <li className="flex gap-3"><span>•</span> To provide and manage your Traveler DNA profile.</li>
                  <li className="flex gap-3"><span>•</span> To generate personalized travel suggestions and itineraries.</li>
                  <li className="flex gap-3"><span>•</span> To communicate with you regarding your alpha access and updates.</li>
                </ul>
              </section>

              <section>
                <h2 className="text-2xl font-bold text-foreground mb-4">4. Data Security</h2>
                <p>
                  We have put in place appropriate security measures to prevent your personal data from being accidentally lost, used or accessed in an unauthorized way, altered or disclosed.
                </p>
              </section>

              <section className="pt-8 border-t border-border">
                <p className="text-sm">Last updated: May 2026</p>
              </section>
            </div>
          </div>
        </div>
      </section>
    </PageWrapper>
  );
}
