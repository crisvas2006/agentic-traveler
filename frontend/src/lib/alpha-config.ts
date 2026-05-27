/**
 * Early-access gating configuration.
 *
 * `ALPHA_CAP` controls how many people receive the welcome email with
 * sign-in instructions. Beyond the cap, signups are still recorded in the
 * `waitlist` table — they just get a "you're on the list" response
 * instead of the email.
 *
 * To open beta, bump this number (e.g. 1000) and update the landing copy
 * accordingly.
 */
export const ALPHA_CAP = 100;
