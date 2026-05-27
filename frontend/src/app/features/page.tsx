import { PageWrapper } from "@/components/layout/PageWrapper";
import { Compass, Zap, Shield, Sparkles, Map, Brain, MessageSquare, Lock } from "lucide-react";
import { cn } from "@/lib/utils";
import { Reveal } from "@/components/ui/Reveal";

const features = [
  {
    icon: Compass,
    title: "Intuitive discovery",
    description: "Say “five days, late spring, want nature and culture, feeling tired.” Get back a shortlist that fits — not the same listicle everyone else gets.",
    color: "bg-purple-500",
  },
  {
    icon: Brain,
    title: "Traveler DNA",
    description: "Odyssey Onboarding builds your Traveler DNA — 15 dimensions of how you actually travel. Every suggestion runs through it.",
    color: "bg-violet-500",
  },
  {
    icon: Zap,
    title: "Live adaptation",
    description: "Weather turns? Energy fades? Tell your companion. Plans bend in real time — no replanning your whole week.",
    color: "bg-purple-600",
  },
  {
    icon: Map,
    title: "Flexible itineraries",
    description: "Day-level plans with alternates for low-energy mornings, weather curveballs, and unexpected second winds.",
    color: "bg-violet-600",
  },
  {
    icon: MessageSquare,
    title: "Telegram companion",
    description: "Your companion lives in your pocket. Send a voice note, drop a photo, get an answer that actually fits the day.",
    color: "bg-purple-500",
  },
  {
    icon: Lock,
    title: "Privacy first",
    description: "Your data is yours. We use it to personalize what you see — never to sell to advertisers.",
  },
];

export default function FeaturesPage() {
  return (
    <PageWrapper>
      <section className="py-20 relative overflow-hidden">
        <div className="container mx-auto px-4 relative z-10">
          <Reveal className="max-w-4xl mx-auto text-center">
            <h1 className="text-4xl md:text-5xl font-bold mb-4 tracking-tight">
              Built for the individual
            </h1>
            <p className="text-lg text-muted-foreground leading-relaxed mb-12">
              Aletheia isn&rsquo;t another booking site. It&rsquo;s a travel companion built around how you actually travel — and built to adapt while you&rsquo;re out there.
            </p>

            <div className="grid md:grid-cols-2 lg:grid-cols-3 gap-6 text-left">
              {features.map((feature, index) => {
                const Icon = feature.icon;
                return (
                  <div
                    key={index}
                    className="p-6 rounded-2xl bg-muted border border-border backdrop-blur-sm hover:border-primary/30 transition-all group hover:bg-background"
                  >
                    <div className={cn("w-10 h-10 rounded-xl flex items-center justify-center mb-5 text-white group-hover:scale-110 transition-transform", feature.color || "bg-primary")}>
                      <Icon className="w-5 h-5" />
                    </div>
                    <h3 className="text-xl font-bold text-foreground mb-2">{feature.title}</h3>
                    <p className="text-sm text-muted-foreground leading-relaxed">
                      {feature.description}
                    </p>
                  </div>
                );
              })}
            </div>
          </Reveal>
        </div>
      </section>
    </PageWrapper>
  );
}
