"use client";

import { PageWrapper } from "@/components/layout/PageWrapper";
import { Cookie } from "lucide-react";
import { cn } from "@/lib/utils";
import { useRef } from "react";
import { useInView } from "@/hooks/use-in-view";

export default function CookiesPage() {
  const headerRef = useRef<HTMLElement>(null);
  const isInView = useInView(headerRef);

  return (
    <PageWrapper>
      <section ref={headerRef} className="py-20 relative overflow-hidden">
        <div className="container mx-auto px-4 relative z-10">
          <div className={cn(
            "max-w-3xl mx-auto transition-all duration-1000",
            isInView ? "opacity-100 translate-y-0" : "opacity-0 translate-y-10"
          )}>
            <div className="flex items-center gap-4 mb-6">
              <Cookie className="w-8 h-8 text-primary" />
              <h1 className="text-3xl md:text-4xl font-bold tracking-tight">
                Cookie Policy
              </h1>
            </div>

            <div className="space-y-10 text-sm text-muted-foreground leading-relaxed">
              <section>
                <h2 className="text-xl font-bold text-foreground mb-3">1. What are Cookies?</h2>
                <p>
                  Cookies are small pieces of text sent to your web browser by a website you visit. A cookie file is stored in your web browser and allows the service or a third-party to recognize you and make your next visit easier and the service more useful to you.
                </p>
              </section>

              <section>
                <h2 className="text-xl font-bold text-foreground mb-3">2. How We Use Cookies</h2>
                <p className="mb-3">
                  When you use and access the Aletheia Travel service, we may place a number of cookies files in your web browser. We use cookies for the following purposes:
                </p>
                <ul className="space-y-2 pl-4">
                  <li className="flex gap-3"><span>•</span> To enable certain functions of the service.</li>
                  <li className="flex gap-3"><span>•</span> To provide analytics.</li>
                  <li className="flex gap-3"><span>•</span> To store your preferences.</li>
                </ul>
              </section>

              <section>
                <h2 className="text-xl font-bold text-foreground mb-3">3. Types of Cookies We Use</h2>
                <p className="mb-3">
                  We use both session and persistent cookies on the service and we use different types of cookies to run the service:
                </p>
                <ul className="space-y-3">
                  <li className="flex gap-3">
                    <span className="font-bold text-foreground shrink-0">• Essential Cookies:</span>
                    <span>We may use essential cookies to authenticate users and prevent fraudulent use of user accounts.</span>
                  </li>
                  <li className="flex gap-3">
                    <span className="font-bold text-foreground shrink-0">• Analytical Cookies:</span>
                    <span>We may use analytical cookies to track information how the service is used so that we can make improvements.</span>
                  </li>
                </ul>
              </section>

              <section className="pt-6 border-t border-border">
                <p className="text-xs">Last updated: May 2026</p>
              </section>
            </div>
          </div>
        </div>
      </section>
    </PageWrapper>
  );
}
