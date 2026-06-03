"""
Supabase client singleton.

Returns a single shared ``supabase.Client`` instance initialized from
SUPABASE_URL and SUPABASE_SERVICE_KEY environment variables.
The service key bypasses RLS and must only be used server-side.
"""

import os
import httpx
from supabase import create_client, Client, ClientOptions

_client: Client | None = None


def get_db() -> Client:
    """Return the shared Supabase client, initializing it on first call."""
    global _client
    if _client is None:
        url = os.environ["SUPABASE_URL"].strip()
        key = os.environ["SUPABASE_SERVICE_KEY"].strip()
        # On Windows, sync HTTP/2 calls inside an ASGI/async environment can raise
        # WinError 10035 (WSAEWOULDBLOCK) due to transport pool conflicts.
        # We explicitly disable HTTP/2 to enforce stable HTTP/1.1.
        opts = ClientOptions(
            httpx_client=httpx.Client(http2=False)
        )
        _client = create_client(url, key, options=opts)
    return _client
