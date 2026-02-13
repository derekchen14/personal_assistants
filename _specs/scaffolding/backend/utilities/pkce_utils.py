import base64
import hashlib
import secrets
from typing import Tuple

"""Utilities for PKCE (Proof Key for Code Exchange) implementation.

This module provides utilities for working with PKCE in OAuth 2.0 authorization.
PKCE is a security extension for OAuth 2.0 authorization code flow that 
mitigates the authorization code interception attack.
"""

def _generate_code_verifier() -> str:
    """Generate a code verifier for PKCE."""
    # Generate a secure random string between 43-128 characters
    token = secrets.token_urlsafe(64)
    # Ensure it's not longer than 128 characters
    return token[:128]

def _generate_code_challenge(code_verifier: str) -> str:
    """Generate code challenge from verifier using S256 method."""
    # SHA256 hash the verifier
    sha256_hash = hashlib.sha256(code_verifier.encode('utf-8')).digest()
    # Base64 URL encode the hash
    code_challenge = base64.urlsafe_b64encode(sha256_hash).decode('utf-8')
    # Remove padding characters
    code_challenge = code_challenge.replace('=', '')
    return code_challenge

def create_pkce_pair() -> Tuple[str, str]:
    """Create a PKCE code verifier and challenge pair."""
    code_verifier = _generate_code_verifier()
    code_challenge = _generate_code_challenge(code_verifier)
    return code_verifier, code_challenge
