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
        <Preview>Welcome to the Aletheia Travel Alpha!</Preview>
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
                Thank you for joining our alpha! You are now part of an exclusive group helping us rethink travel planning - focusing on energy levels, motivations, and life phases rather than just finding the cheapest flight.
              </Text>

              <Heading as="h3" className="text-lg font-bold text-slate-900 mb-4">
                Get Started in 3 Steps:
              </Heading>

              <Section className="mb-8">
                <Text className="text-sm text-slate-700 mb-4">
                  <strong className="text-blue-600">1. Access your Companion:</strong> Use the link below to open our companion (currently via Telegram).
                </Text>
                <Text className="text-sm text-slate-700 mb-4">
                  <strong className="text-blue-600">2. Define your Traveler DNA:</strong> Start the bot and complete the short onboarding form. This allows our agents to understand what truly makes a trip meaningful for you.
                </Text>
                <Text className="text-sm text-slate-700 mb-4">
                  <strong className="text-blue-600">3. Chat Naturally:</strong> Tell the bot how you feel. Try: <em className="text-slate-500">"I'm feeling adventurous but have low energy today"</em> or <em className="text-slate-500">"Plan a 3-day quiet escape."</em>
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
                  Start Your Journey
                </Button>
              </Section>

              <Section className="bg-slate-50 rounded-lg p-6 mb-8 border border-slate-100">
                <Text className="text-sm text-slate-600 leading-relaxed m-0 italic">
                  <strong>Coming Soon:</strong> We are currently building a full web interface to complement the mobile experience. We'll send you updates as we roll out new features!
                </Text>
              </Section>

              <Hr className="border-slate-100 my-8" />

              <Text className="text-sm text-slate-500 mb-1">
                Safe travels,
              </Text>
              <Text className="text-sm font-semibold text-slate-900">
                The Aletheia Travel Team
              </Text>
            </Section>

            <Text className="text-[10px] text-center text-slate-400 mt-8 uppercase tracking-widest">
              Aletheia Travel Alpha • This email was sent to {email}, if you didn't sign up for this email, you can safely ignore it.
            </Text>
          </Container>
        </Body>
      </Html>
    </Tailwind>
  );
};

export default AlphaWelcomeEmail;
