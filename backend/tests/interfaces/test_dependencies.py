"""
Tests for JWT and authorization dependencies.
"""

import os
from unittest.mock import MagicMock, patch
import pytest
from fastapi import HTTPException
import jwt

from agentic_traveler.interfaces.dependencies import (
    get_jwk_client,
    verify_supabase_jwt,
    WebUserCtx,
)


def test_get_jwk_client_creates_correct_url():
    """get_jwk_client correctly points to the Supabase JWKS endpoint with apikey header."""
    # Temporarily reset global state for testing
    import agentic_traveler.interfaces.dependencies as deps
    deps._jwk_client = None

    env_mock = {
        "SUPABASE_URL": "https://test-project.supabase.co/",
        "SUPABASE_SERVICE_KEY": "test-service-key-xyz"
    }

    with patch.dict(os.environ, env_mock):
        client = get_jwk_client()
        assert isinstance(client, jwt.PyJWKClient)
        assert client.uri == "https://test-project.supabase.co/auth/v1/.well-known/jwks.json"
        assert client.headers == {"apikey": "test-service-key-xyz"}

    # Reset again
    deps._jwk_client = None


def test_verify_supabase_jwt_success():
    """verify_supabase_jwt successfully decodes a valid RS256 token using dynamic JWKS."""
    import agentic_traveler.interfaces.dependencies as deps
    deps._jwk_client = None

    token = "Bearer test.jwt.token"
    mock_payload = {
        "sub": "user-uuid-12345",
        "email": "traveler@example.com",
        "role": "authenticated",
    }

    # Mock the JWK client and token decoder
    mock_signing_key = MagicMock()
    mock_signing_key.key = "mock-public-key-content"

    with patch("agentic_traveler.interfaces.dependencies.get_jwk_client") as mock_get_client, \
         patch("jwt.decode", return_value=mock_payload) as mock_decode, \
         patch.dict(os.environ, {"SUPABASE_URL": "https://test-project.supabase.co"}):
        
        # Configure JWK client to return a mock key
        mock_jwk = MagicMock()
        mock_jwk.get_signing_key_from_jwt.return_value = mock_signing_key
        mock_get_client.return_value = mock_jwk

        result = verify_supabase_jwt(authorization=token)

        # Verify correct context was returned
        assert isinstance(result, WebUserCtx)
        assert result.user_id == "user-uuid-12345"
        assert result.auth_id == "user-uuid-12345"
        assert result.email == "traveler@example.com"

        # Verify signing key was fetched from token
        mock_jwk.get_signing_key_from_jwt.assert_called_once_with("test.jwt.token")

        # Verify decode was called with RS256 and ES256 algorithms and retrieved key
        mock_decode.assert_called_once_with(
            "test.jwt.token",
            "mock-public-key-content",
            algorithms=["RS256", "ES256"],
            audience="authenticated",
        )


def test_verify_supabase_jwt_missing_bearer():
    """verify_supabase_jwt raises 401 for malformed Authorization headers."""
    with pytest.raises(HTTPException) as exc_info:
        verify_supabase_jwt(authorization="InvalidTokenFormat")
    assert exc_info.value.status_code == 401
    assert "Missing bearer token" in exc_info.value.detail


def test_verify_supabase_jwt_expired():
    """verify_supabase_jwt raises 401 for expired tokens."""
    import agentic_traveler.interfaces.dependencies as deps
    deps._jwk_client = None

    token = "Bearer expired.jwt.token"
    mock_signing_key = MagicMock()
    mock_signing_key.key = "mock-public-key-content"

    with patch("agentic_traveler.interfaces.dependencies.get_jwk_client") as mock_get_client, \
         patch("jwt.decode", side_effect=jwt.ExpiredSignatureError), \
         patch.dict(os.environ, {"SUPABASE_URL": "https://test-project.supabase.co"}):
        
        mock_jwk = MagicMock()
        mock_jwk.get_signing_key_from_jwt.return_value = mock_signing_key
        mock_get_client.return_value = mock_jwk

        with pytest.raises(HTTPException) as exc_info:
            verify_supabase_jwt(authorization=token)
        assert exc_info.value.status_code == 401
        assert "Token expired" in exc_info.value.detail
