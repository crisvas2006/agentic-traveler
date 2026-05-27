import * as React from 'react';
import {
  Html,
  Head,
  Preview,
  Body,
  Container,
  Section,
  Text,
  Heading,
  Hr,
  Link,
  Button,
  Tailwind,
} from '@react-email/components';

interface AlphaWelcomeEmailProps {
  email: string;
}

export const AlphaWelcomeEmail = ({ email }: AlphaWelcomeEmailProps) => {
  const telegramUrl = "https://t.me/TripGenieCompanionBot";

  return (
    <Tailwind>
      <Html>
        <Head />
        <Preview>You&rsquo;re in. Here&rsquo;s how to start your first journey.</Preview>
        <Body className="bg-slate-50 font-sans py-8">
          <Container className="mx-auto px-4">
            <Section className="bg-white rounded-xl shadow-sm border border-slate-200 p-8 md:p-12 max-w-2xl mx-auto">
              <Heading className="text-2xl font-bold text-slate-900 mb-6 tracking-tight text-center">
                Welcome to <span className="text-blue-600">Aletheia Travel</span>
              </Heading>

              <Text className="text-base text-slate-700 leading-relaxed mb-6">
                Hi there,
              </Text>

              <Text className="text-base text-slate-700 leading-relaxed mb-8">
                You&rsquo;re in. You&rsquo;ve got one of the first 100 early-access seats — thanks for jumping in this early. Aletheia plans trips around who you actually are, not the average tourist: your energy, your motivations, and the season of life you&rsquo;re in.
              </Text>

              <Heading as="h3" className="text-lg font-bold text-slate-900 mb-4">
                Three steps to your first plan
              </Heading>

              <Section className="mb-8">
                <Text className="text-sm text-slate-700 mb-4">
                  <strong className="text-blue-600">1. Open your companion.</strong> Use the link below to start chatting on Telegram. A native web chat is in development.
                </Text>
                <Text className="text-sm text-slate-700 mb-4">
                  <strong className="text-blue-600">2. Build your Traveler DNA.</strong> Start the bot and run the short onboarding — 15 dimensions of how you actually like to travel. Every suggestion runs through it.
                </Text>
                <Text className="text-sm text-slate-700 mb-4">
                  <strong className="text-blue-600">3. Talk to it like a friend.</strong> Try: <em className="text-slate-500">&ldquo;feeling adventurous but low energy today&rdquo;</em> or <em className="text-slate-500">&ldquo;plan a 3-day quiet escape, end of May.&rdquo;</em>
                </Text>
              </Section>

              <Section className="text-center mb-10">
                <Button
                  href={telegramUrl}
                  style={{
                    backgroundColor: '#2563eb',
                    borderRadius: '8px',
                    color: '#ffffff',
                    fontSize: '15px',
                    fontWeight: 'bold',
                    textDecoration: 'none',
                    textAlign: 'center',
                    display: 'inline-block',
                    padding: '14px 32px',
                    lineHeight: '120%',
                  }}
                >
                  Start your journey
                </Button>
              </Section>

              <Section className="bg-slate-50 rounded-lg p-6 mb-8 border border-slate-100">
                <Text className="text-sm text-slate-600 leading-relaxed m-0 italic">
                  <strong>In active development:</strong> a full web home where you can review your Traveler DNA, browse itineraries, and chat with your companion alongside the map. We&rsquo;ll write when it&rsquo;s ready — no marketing blasts.
                </Text>
              </Section>

              <Hr className="border-slate-100 my-8" />

              <Text className="text-sm text-slate-500 mb-1">
                Safe travels,
              </Text>
              <Text className="text-sm font-semibold text-slate-900">
                Cristian — Aletheia Travel
              </Text>
            </Section>

            <Text className="text-[10px] text-center text-slate-400 mt-8 uppercase tracking-widest">
              Aletheia Travel • Sent to {email}. If this wasn&rsquo;t you, ignore it — no further mail.
            </Text>
          </Container>
        </Body>
      </Html>
    </Tailwind>
  );
};

export default AlphaWelcomeEmail;
