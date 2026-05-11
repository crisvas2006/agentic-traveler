"use client";
// Force refresh for icons


import { PageWrapper } from "@/components/layout/PageWrapper";
import { Globe, Code, Sparkles } from "lucide-react";
import { cn } from "@/lib/utils";
import { useRef } from "react";
import { useInView } from "@/hooks/use-in-view";
import Image from "next/image";

export default function AboutPage() {
  const headerRef = useRef<HTMLElement>(null);
  const isInView = useInView(headerRef);

  return (
    <PageWrapper>
      <section ref={headerRef} className="py-20 relative overflow-hidden">
        <div className="container mx-auto px-4 relative z-10">
          <div className={cn(
            "max-w-4xl mx-auto transition-all duration-1000",
            isInView ? "opacity-100 translate-y-0" : "opacity-0 translate-y-10"
          )}>
            <div className="text-center mb-16">
              <h1 className="text-4xl md:text-5xl font-bold mb-4 tracking-tight">
                About the Project
              </h1>
              <p className="text-lg text-muted-foreground leading-relaxed max-w-2xl mx-auto">
                Aletheia Travel is a vision for a more intentional, personalized way to explore our world.
              </p>
            </div>

            <div className="grid md:grid-cols-2 gap-12 ">
              <div className="relative group">
                <div className="absolute -inset-4 bg-gradient-to-tr from-primary/20 to-purple-600/20 rounded-full opacity-20 blur-2xl group-hover:opacity-40 transition-opacity" />
                <div className="relative w-full aspect-square max-w-[240px] mx-auto rounded-full overflow-hidden border-4 border-primary/20 shadow-2xl">
                  <Image
                    src="/founder.jpg?v=2"
                    alt="Cristian - Founder of Aletheia Travel"
                    fill
                    sizes="(max-width: 768px) 100vw, 240px"
                    className="object-cover"
                  />
                </div>
                <div className="relative z-10 mt-6 text-center">
                  <h2 className="text-2xl font-bold text-foreground mb-1">Cristian Dumitrascu</h2>
                  <p className="text-primary font-medium mb-4 uppercase tracking-wider text-xs">Founder & Solo Developer</p>

                  <div className="flex justify-center gap-3">
                    <a href="https://www.linkedin.com/in/vasile-cristian-dumitrascu/" target="_blank" rel="noopener noreferrer" className="p-2.5 rounded-full bg-primary/10 border border-primary/20 text-primary hover:bg-primary/20 transition-all">
                      <Globe className="w-5 h-5" />
                    </a>
                    <a href="https://github.com/crisvas2006/agentic-traveler" target="_blank" rel="noopener noreferrer" className="p-2.5 rounded-full bg-primary/10 border border-primary/20 text-primary hover:bg-primary/20 transition-all">
                      <Code className="w-5 h-5" />
                    </a>
                  </div>
                </div>
              </div>

              <div className="space-y-5 text-base text-muted-foreground leading-relaxed">
                <p>
                  Aletheia Travel started from a simple frustration: planning for a trip takes hours or even days and getting off the standard tourist path in order to follow my individual pursuits takes even more energy and research, and many times there are things I cannot even think about that would make my trip more enjoyable.
                </p>
                <p>
                  As a solo developer, I wanted to build something that felt like a true companion: an intelligent system that actually knows who you are, what you value, and how you feel in the moment.
                </p>
                <p>
                  This project combines state-of-the-art agentic AI with a deep commitment to personalization. Every line of code is written with the goal of helping you plan next trip your way, seamlessly.
                </p>
                <div className="pt-5 border-t border-border">
                  <div className="flex items-center gap-3 text-primary font-bold italic text-sm">
                    <Sparkles className="w-4 h-4" />
                    "The journey is the reward, but the companion makes the difference."
                  </div>
                </div>
              </div>
            </div>
          </div>
        </div>
      </section>
    </PageWrapper>
  );
}
