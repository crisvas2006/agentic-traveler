"use client";

import { PageWrapper } from "@/components/layout/PageWrapper";
import { HelpCircle, ChevronDown } from "lucide-react";
import { cn } from "../../lib/utils";
import { useState } from "react";
import { Reveal } from "@/components/ui/Reveal";

const faqs = [
  {
    question: "What exactly is Aletheia Travel?",
    answer: "Aletheia Travel is an agentic AI travel companion. Unlike simple chatbots, it uses a multi-agent system to understand your unique 'Traveler DNA' and provides personalized discovery, planning, and real-time assistance during your trip.",
  },
  {
    question: "How is it different from ChatGPT?",
    answer: "ChatGPT is a general-purpose model. Aletheia Travel is a specialized travel system that uses multiple agents (Discovery, Planner, Companion) and maintains long-term memory of your preferences. It also integrates real-world data like weather and events specifically for your itinerary.",
  },
  {
    question: "Does Aletheia Travel book flights or hotels for me?",
    answer: "Not directly. We provide a full itinerary and suggest the best options that fit your profile. Actual booking will be done by you on your preferred platforms.",
  },
  {
    question: "Why do I need to use Telegram?",
    answer: "During the alpha phase, Telegram provides the most reliable, mobile-first experience for a companion that needs to travel with you. A native web chat is currently in development.",
  },
  {
    question: "Is it really free?",
    answer: "Alpha access is free! We grant a credit allowance to new users which is sufficient for planning a complete trip. We may introduce paid tiers as we scale, but alpha pioneers will always have a special place in our ecosystem.",
  },
  {
    question: "What happens if the weather turns bad during my trip?",
    answer: "That's where the 'Companion' agent shines. Just tell the bot your situation, and it will immediately suggest indoor alternatives or schedule adjustments that fit your mood and Traveler DNA.",
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
                <span className="text-xs text-primary font-medium uppercase tracking-wider">Have Questions?</span>
              </div>
              <h1 className="text-4xl md:text-5xl font-bold mb-4 tracking-tight">
                Frequently Asked
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
