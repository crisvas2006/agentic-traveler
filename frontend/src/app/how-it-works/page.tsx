import { PageWrapper } from "@/components/layout/PageWrapper";
import { ListChecks, Brain, MessageSquare, Globe } from "lucide-react";
import { Reveal } from "@/components/ui/Reveal";

const steps = [
  {
    icon: ListChecks,
    title: "Odyssey Onboarding",
    description: "A deep-dive intake on how you actually travel — energy levels, risk tolerance, what makes a trip feel right. About four minutes.",
  },
  {
    icon: Brain,
    title: "Traveler DNA mapping",
    description: "Your answers become your Traveler DNA — a structured profile across 15 dimensions that filters every suggestion we ever make for you.",
  },
  {
    icon: MessageSquare,
    title: "Chat with your companion",
    description: "On Telegram for now — fast, mobile-first, always with you. A native web chat is in development.",
  },
];

export default function HowItWorksPage() {
  return (
    <PageWrapper>
      <section className="py-20 relative overflow-hidden">
        <div className="container mx-auto px-4 relative z-10">
          <Reveal className="max-w-4xl mx-auto">
            <div className="text-center mb-16">
              <h1 className="text-4xl md:text-5xl font-bold mb-4 tracking-tight">
                How it works
              </h1>
              <p className="text-lg text-muted-foreground leading-relaxed max-w-2xl mx-auto">
                From the Odyssey Onboarding to live trip adaptation — here&rsquo;s how Aletheia plans with you, not for you.
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
                In active development: a full web home
              </h2>
              <p className="text-muted-foreground text-base mb-0 leading-relaxed">
                Telegram is the heart of the early-access experience today. We&rsquo;re also building a web dashboard where you can review your Traveler DNA, browse itineraries, and chat with your companion alongside the map.
              </p>
            </div>
          </Reveal>
        </div>
      </section>
    </PageWrapper>
  );
}
