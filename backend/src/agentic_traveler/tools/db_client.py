"""
Supabase client singleton.

Returns a single shared ``supabase.Client`` instance initialized from
SUPABASE_URL and SUPABASE_SERVICE_KEY environment variables.
The service key bypasses RLS and must only be used server-side.
"""

import logging
import os
import sys
import httpx
from supabase import create_client, Client, ClientOptions

logger = logging.getLogger(__name__)

_client: Client | None = None


def get_db() -> Client:
    """Return the shared Supabase client, initializing it on first call."""
    global _client
    if _client is None:
        url = os.environ["SUPABASE_URL"].strip()
        key = os.environ["SUPABASE_SERVICE_KEY"].strip()
        # On Windows, sync HTTP/2 calls inside an ASGI/async environment can raise
        # WinError 10035 (WSAEWOULDBLOCK) due to transport pool conflicts.
        # We explicitly disable HTTP/2 on Windows, but enable it on Linux (Cloud Run)
        # where the transport is verified safe and HTTP/2 gives better connection reuse.
        is_windows = sys.platform.startswith("win")
        http2_enabled = not is_windows
        opts = ClientOptions(
            httpx_client=httpx.Client(http2=http2_enabled)
        )
        _client = create_client(url, key, options=opts)
        # Single startup log line so production deploys can confirm which transport
        # was negotiated. Useful when debugging connection issues across platforms.
        logger.info(
            "Supabase client initialized: platform=%s http2=%s url_host=%s",
            sys.platform,
            http2_enabled,
            url.split("//", 1)[-1].split("/", 1)[0],
        )
    return _client
