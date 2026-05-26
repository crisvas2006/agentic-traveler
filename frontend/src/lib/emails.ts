/**
 * Server-side email rendering utilities.
 * Import only from Server Components and Route Handlers — never from client code.
 */
import * as React from "react";
import { render } from "@react-email/components";
import { AlphaWelcomeEmail } from "@/emails/AlphaWelcomeEmail";

/** Renders the alpha welcome email to an HTML string. */
export async function renderAlphaWelcomeEmail(email: string): Promise<string> {
  return render(React.createElement(AlphaWelcomeEmail, { email }));
}
