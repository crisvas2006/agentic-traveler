import { createServerClient } from '@supabase/ssr'
import { NextResponse, type NextRequest } from 'next/server'

export default async function proxy(request: NextRequest) {
  try {
    let supabaseResponse = NextResponse.next({ request })

    const supabase = createServerClient(
      process.env.NEXT_PUBLIC_SUPABASE_URL!,
      process.env.NEXT_PUBLIC_SUPABASE_PUBLISHABLE_KEY!,
      {
        cookies: {
          getAll() {
            return request.cookies.getAll()
          },
          setAll(cookiesToSet) {
            cookiesToSet.forEach(({ name, value }) =>
              request.cookies.set(name, value)
            )
            supabaseResponse = NextResponse.next({ request })
            cookiesToSet.forEach(({ name, value, options }) =>
              supabaseResponse.cookies.set(name, value, options)
            )
          },
        },
      }
    )

    // Refreshes the session cookie AND returns the current user.
    // getUser() validates the JWT server-side — never use getSession() here.
    const { data: { user } } = await supabase.auth.getUser()

    // Protect /dashboard and /guide — redirect unauthenticated visitors to /login
    if ((request.nextUrl.pathname.startsWith('/dashboard') || request.nextUrl.pathname.startsWith('/guide')) && !user) {
      const url = request.nextUrl.clone()
      url.pathname = '/login'
      return NextResponse.redirect(url)
    }

    // Skip auth pages — redirect already-authenticated visitors to /dashboard.
    // This is what makes the back button feel sane: if a logged-in user lands
    // on /login, /sign-up, or the landing page (e.g. by pressing back from
    // /dashboard), they bounce straight to /dashboard instead of seeing a
    // login form they don't need.
    const AUTHED_BOUNCE_PATHS = ['/login', '/sign-up', '/']
    if (user && AUTHED_BOUNCE_PATHS.includes(request.nextUrl.pathname)) {
      const url = request.nextUrl.clone()
      url.pathname = '/dashboard'
      return NextResponse.redirect(url)
    }

    return supabaseResponse
  } catch {
    // If the auth check fails for any reason, pass the request through.
    // The page-level session check acts as a second line of defence.
    return NextResponse.next({ request })
  }
}

export const config = {
  matcher: [
    '/((?!_next/static|_next/image|favicon.ico|.*\\.(?:svg|png|jpg|jpeg|gif|webp)$).*)',
  ],
}
