"use client";

import { PageWrapper } from "@/components/layout/PageWrapper";
import { HelpCircle, ChevronDown } from "lucide-react";
import { cn } from "@/lib/utils";
import { useRef, useState } from "react";
import { useInView } from "@/hooks/use-in-view";

const faqs = [
  {
    question: "What exactly is Trip Genie?",
    answer: "Trip Genie is an agentic AI travel companion. Unlike simple chatbots, it uses a multi-agent system to understand your unique 'Traveler DNA' and provides personalized discovery, planning, and real-time assistance during your trip.",
  },
  {
    question: "How is it different from ChatGPT?",
    answer: "ChatGPT is a general-purpose model. Trip Genie is a specialized travel system that uses multiple agents (Discovery, Planner, Companion) and maintains long-term memory of your preferences. It also integrates real-world data like weather and events specifically for your itinerary.",
  },
  {
    question: "Does Trip Genie book flights or hotels for me?",
    answer: "Not directly. We provide a full itinerary and suggest the best options that fit your profile. We provide links and details so you can book on your preferred platforms with full confidence.",
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
  const headerRef = useRef<HTMLElement>(null);
  const isInView = useInView(headerRef);
  const [openIndex, setOpenIndex] = useState<number | null>(0);

  return (
    <PageWrapper>
      <section ref={headerRef} className="py-24 relative overflow-hidden">
        <div className="container mx-auto px-4 relative z-10">
          <div className={cn(
            "max-w-3xl mx-auto transition-all duration-1000",
            isInView ? "opacity-100 translate-y-0" : "opacity-0 translate-y-10"
          )}>
            <div className="text-center mb-20">
              <div className="inline-flex items-center gap-2 px-4 py-2 rounded-full bg-primary/10 border border-primary/20 backdrop-blur-sm mb-6">
                <HelpCircle className="w-4 h-4 text-primary" />
                <span className="text-sm text-primary font-medium uppercase tracking-wider">Have Questions?</span>
              </div>
              <h1 className="text-5xl md:text-6xl font-bold mb-6 tracking-tight">
                Frequently Asked
              </h1>
            </div>

            <div className="space-y-4">
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
                    className="w-full px-8 py-6 flex items-center justify-between text-left"
                  >
                    <span className="text-lg font-bold text-foreground">{faq.question}</span>
                    <ChevronDown className={cn("w-5 h-5 text-primary transition-transform", openIndex === index && "rotate-180")} />
                  </button>
                  <div className={cn(
                    "overflow-hidden transition-all duration-300",
                    openIndex === index ? "max-h-96 opacity-100" : "max-h-0 opacity-0"
                  )}>
                    <div className="px-8 pb-6 text-muted-foreground leading-relaxed">
                      {faq.answer}
                    </div>
                  </div>
                </div>
              ))}
            </div>
          </div>
        </div>
      </section>
    </PageWrapper>
  );
}
