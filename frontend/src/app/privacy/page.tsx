import { PageWrapper } from "@/components/layout/PageWrapper";
import { Shield } from "lucide-react";
import { Reveal } from "@/components/ui/Reveal";

export default function PrivacyPage() {
  return (
    <PageWrapper>
      <section className="py-20 relative overflow-hidden">
        <div className="container mx-auto px-4 relative z-10">
          <Reveal className="max-w-3xl mx-auto">
            <div className="flex items-center gap-4 mb-6">
              <Shield className="w-8 h-8 text-primary" />
              <h1 className="text-3xl md:text-4xl font-bold tracking-tight">
                Privacy Policy
              </h1>
            </div>

            <div className="space-y-10 text-sm text-muted-foreground leading-relaxed">
              <section>
                <h2 className="text-xl font-bold text-foreground mb-3">1. Introduction</h2>
                <p>
                  At Aletheia Travel, we respect your privacy and are committed to protecting your personal data. This privacy policy will inform you as to how we look after your personal data when you visit our website or use our Telegram companion.
                </p>
              </section>

              <section>
                <h2 className="text-xl font-bold text-foreground mb-3">2. The Data We Collect</h2>
                <p className="mb-3">
                  We may collect, use, store and transfer different kinds of personal data about you which we have grouped together as follows:
                </p>
                <ul className="space-y-3">
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
                <h2 className="text-xl font-bold text-foreground mb-3">3. How We Use Your Data</h2>
                <p className="mb-3">
                  We will only use your personal data when the law allows us to. Most commonly, we will use your personal data in the following circumstances:
                </p>
                <ul className="space-y-2 pl-4">
                  <li className="flex gap-3"><span>•</span> To provide and manage your Traveler DNA profile.</li>
                  <li className="flex gap-3"><span>•</span> To generate personalized travel suggestions and itineraries.</li>
                  <li className="flex gap-3"><span>•</span> To communicate with you regarding your alpha access and updates.</li>
                </ul>
              </section>

              <section>
                <h2 className="text-xl font-bold text-foreground mb-3">4. Data Security</h2>
                <p>
                  We have put in place appropriate security measures to prevent your personal data from being accidentally lost, used or accessed in an unauthorized way, altered or disclosed.
                </p>
              </section>

              <section>
                <h2 className="text-xl font-bold text-foreground mb-3">5. Third-Party Processors</h2>
                <p className="mb-3">
                  We share data with the following third-party processors to deliver and monitor our services:
                </p>
                <ul className="space-y-3">
                  <li className="flex gap-3">
                    <span className="font-bold text-foreground shrink-0">• Google Vertex AI / Gemini:</span>
                    <span>Processes chat prompts and replies.</span>
                  </li>
                  <li className="flex gap-3">
                    <span className="font-bold text-foreground shrink-0">• Supabase:</span>
                    <span>Stores user accounts, preferences, trips, and message logs in the EU (eu-central-1).</span>
                  </li>
                  <li className="flex gap-3">
                    <span className="font-bold text-foreground shrink-0">• Resend:</span>
                    <span>Sends emails within the EU. Only email address is processed, no other user data.</span>
                  </li>
                  <li className="flex gap-3">
                    <span className="font-bold text-foreground shrink-0">• Telegram:</span>
                    <span>Processes messages sent through the Telegram channel interface, if you choose to use this interface.</span>
                  </li>
                  <li className="flex gap-3">
                    <span className="font-bold text-foreground shrink-0">• LangSmith (LangChain Inc.):</span>
                    <span>Monitors LLM traces, prompts, replies, and tool calls in the EU (Frankfurt). Data is tagged only with an HMAC-hashed user ID (no email, name, phone, telegram handle, or JWT) and retained for a rolling 14 days.</span>
                  </li>
                </ul>
                <p className="mt-4 text-xs text-muted-foreground leading-relaxed">
                  <strong>Important Notice:</strong> We share this data specifically to generate personalized travel suggestions, build day-by-day itineraries, and monitor system performance and safety logs in real time. Because your chat prompts and the AI's replies are processed by these services to fulfill your requests, <strong>you must not type or paste passwords, credit cards, or other sensitive secrets into the chat interface.</strong>
                </p>
              </section>

              <section className="pt-6 border-t border-border">
                <p className="text-xs">Last updated: June 2026</p>
              </section>
            </div>
          </Reveal>
        </div>
      </section>
    </PageWrapper>
  );
}
