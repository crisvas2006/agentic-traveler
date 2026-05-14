"""
Supabase client singleton.

Returns a single shared ``supabase.Client`` instance initialized from
SUPABASE_URL and SUPABASE_SERVICE_KEY environment variables.
The service key bypasses RLS and must only be used server-side.
"""

import os
from supabase import create_client, Client

_client: Client | None = None


def get_db() -> Client:
    """Return the shared Supabase client, initializing it on first call."""
    global _client
    if _client is None:
        url = os.environ["SUPABASE_URL"].strip()
        key = os.environ["SUPABASE_SERVICE_KEY"].strip()
        _client = create_client(url, key)
    return _client
