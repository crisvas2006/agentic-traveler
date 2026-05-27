"use client";

import { PageWrapper } from "@/components/layout/PageWrapper";
import { HelpCircle, ChevronDown } from "lucide-react";
import { cn } from "../../lib/utils";
import { useState } from "react";
import { Reveal } from "@/components/ui/Reveal";

const faqs = [
  {
    question: "What exactly is Aletheia Travel?",
    answer: "A travel companion that actually adapts to you. Most planners optimize for the cheapest flight; Aletheia uses your Traveler DNA — 15 dimensions of how you like to travel — to plan trips that fit your real life.",
  },
  {
    question: "How is it different from ChatGPT?",
    answer: "ChatGPT is general-purpose. Aletheia is built specifically for travel — it remembers your preferences, pulls in real-world weather and events, and runs three specialized models (one for discovery, one for planning, one for live trip adaptation) that hand off to each other.",
  },
  {
    question: "Does Aletheia book flights or hotels for me?",
    answer: "Not yet. You get a full itinerary with concrete suggestions; the booking happens on your preferred platforms. Auto-booking is on the roadmap, not in this release.",
  },
  {
    question: "Why do I need to use Telegram?",
    answer: "For now, Telegram is the most reliable way to keep a companion in your pocket while you travel. A native web chat is in development.",
  },
  {
    question: "Is it really free?",
    answer: "Early access is free. Every new traveler gets an amount of credits — enough to fully plan a trip. Paid tiers may come later, but early-access travelers keep their place.",
  },
  {
    question: "What happens if the weather turns bad during my trip?",
    answer: "Message your companion. It pulls indoor options forward, pushes outdoor plans back, and rebalances the day around your energy and your Traveler DNA.",
  },
];

export default function FAQPage() {
  const [openIndex, setOpenIndex] = useState<number | null>(0);

  return (
    <PageWrapper>
      <section className="py-20 relative overflow-hidden">
        <div className="container mx-auto px-4 relative z-10">
          <Reveal className="max-w-3xl mx-auto">
            <div className="text-center mb-16">
              <div className="inline-flex items-center gap-2 px-3 py-1.5 rounded-full bg-primary/10 border border-primary/20 backdrop-blur-sm mb-4">
                <HelpCircle className="w-3.5 h-3.5 text-primary" />
                <span className="text-xs text-primary font-medium uppercase tracking-wider">Have questions</span>
              </div>
              <h1 className="text-4xl md:text-5xl font-bold mb-4 tracking-tight">
                Frequently asked
              </h1>
            </div>

            <div className="space-y-3">
              {faqs.map((faq, index) => (
                <div
                  key={index}
                  className={cn(
                    "rounded-2xl border transition-all duration-300",
                    openIndex === index
                      ? "bg-muted border-primary/30"
                      : "bg-muted/50 border-border hover:border-primary/20"
                  )}
                >
                  <button
                    onClick={() => setOpenIndex(openIndex === index ? null : index)}
                    className="w-full px-6 py-4 flex items-center justify-between text-left"
                  >
                    <span className="text-base font-bold text-foreground">{faq.question}</span>
                    <ChevronDown className={cn("w-4 h-4 text-primary transition-transform", openIndex === index && "rotate-180")} />
                  </button>
                  <div className={cn(
                    "overflow-hidden transition-all duration-300",
                    openIndex === index ? "max-h-96 opacity-100" : "max-h-0 opacity-0"
                  )}>
                    <div className="px-6 pb-4 text-sm text-muted-foreground leading-relaxed">
                      {faq.answer}
                    </div>
                  </div>
                </div>
              ))}
            </div>
          </Reveal>
        </div>
      </section>
    </PageWrapper>
  );
}
