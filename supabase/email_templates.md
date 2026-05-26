# Email Templates

Configure in: **Supabase → Authentication → Email Templates**

All templates use the Supabase built-in variable syntax `{{ .Variable }}`.

---

## Confirm signup

**Subject:** Confirm your Aletheia Travel account

**Where to set:** Auth → Email Templates → Confirm signup

```html
<h2>Welcome to Aletheia Travel</h2>
<p>Thanks for signing up. Click the link below to confirm your email address:</p>
<p><a href="{{ .ConfirmationURL }}">Confirm my account</a></p>
<p>This link expires in 24 hours. If you didn't sign up, you can safely ignore this email.</p>
```

---

## Reset password

**Subject:** Reset your Aletheia Travel password

**Where to set:** Auth → Email Templates → Reset password

```html
<h2>Reset your password</h2>
<p>We received a request to reset the password for your Aletheia Travel account.</p>
<p><a href="{{ .ConfirmationURL }}">Reset my password</a></p>
<p>This link expires in 1 hour. If you didn't request a reset, you can safely ignore this email.</p>
```

---

## Magic link (if enabled)

**Subject:** Your Aletheia Travel login link

**Where to set:** Auth → Email Templates → Magic link

```html
<h2>Your login link</h2>
<p>Click the link below to sign in to Aletheia Travel. It expires in 1 hour.</p>
<p><a href="{{ .ConfirmationURL }}">Sign in</a></p>
```

---

## Notes

- Supabase's default branding can be replaced in **Auth → SMTP Settings** with a custom sender name/email (e.g. `Aletheia Travel <hello@aletheia.travel>`).
- For production, configure a custom SMTP provider (e.g. Resend) in **Project Settings → Auth → SMTP**.
- The Resend integration is already used by the backend for other emails — reuse the same API key.
