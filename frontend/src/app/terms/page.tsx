"use client";

import { PageWrapper } from "@/components/layout/PageWrapper";
import { FileText } from "lucide-react";
import { cn } from "@/lib/utils";
import { useRef } from "react";
import { useInView } from "@/hooks/use-in-view";

export default function TermsPage() {
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
              <FileText className="w-8 h-8 text-primary" />
              <h1 className="text-3xl md:text-4xl font-bold tracking-tight">
                Terms of Service
              </h1>
            </div>

            <div className="space-y-10 text-sm text-muted-foreground leading-relaxed">
              <section>
                <h2 className="text-xl font-bold text-foreground mb-3">1. Agreement to Terms</h2>
                <p>
                  By accessing our website and using the Aletheia Travel alpha service, you agree to be bound by these Terms of Service. If you do not agree to all of these terms, you are prohibited from using the site and service.
                </p>
              </section>

              <section>
                <h2 className="text-xl font-bold text-foreground mb-3">2. Alpha Phase Disclaimer</h2>
                <p>
                  Aletheia Travel is currently in an alpha development phase. The service is provided "as is" and "as available" without any warranties of any kind. We do not guarantee that the service will be uninterrupted, error-free, or completely accurate in its suggestions.
                </p>
              </section>

              <section>
                <h2 className="text-xl font-bold text-foreground mb-3">3. Credit System</h2>
                <p>
                  Access to our agents is governed by a credit system. We reserve the right to modify credit allowances, deduction rates, and the overall economy of the system at any time during the alpha phase.
                </p>
              </section>

              <section>
                <h2 className="text-xl font-bold text-foreground mb-3">4. Limitation of Liability</h2>
                <p>
                  In no event shall Aletheia Travel or its founder be liable for any damages (including, without limitation, damages for loss of data or profit, or due to business interruption) arising out of the use or inability to use the materials on our website or Telegram service.
                </p>
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
