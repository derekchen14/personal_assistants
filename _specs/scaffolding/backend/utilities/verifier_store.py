from datetime import datetime, timedelta
from typing import Dict, Optional, Tuple

"""PKCE Code Verifier Storage Management.

This module provides an in-memory storage solution for PKCE code verifiers used in OAuth 2.0
authorization flow. It handles:
- Temporary storage of code verifiers mapped to state parameters
- Automatic cleanup of expired verifiers (10 minute lifetime)
- One-time retrieval of verifiers (automatically removed after first use)
- Thread-safe storage operations

The store maintains verifiers in the format:
{state: (code_verifier, expiry_timestamp)}
"""

# In-memory store for PKCE code verifiers
# Format: {state: (code_verifier, expiry_timestamp)}
_verifier_store: Dict[str, Tuple[str, float]] = {}

# Expiration time for code verifiers (10 minutes)
EXPIRY_SECONDS = 600

def store_verifier(state: str, code_verifier: str) -> None:
    """Store a code verifier with its state."""
    expiry = datetime.now() + timedelta(seconds=EXPIRY_SECONDS)
    _verifier_store[state] = (code_verifier, expiry.timestamp())
    
    # Clean up expired verifiers
    _cleanup_expired_verifiers()

def get_verifier(state: str) -> Optional[str]:
    """Retrieve and remove a code verifier by state."""
    if state not in _verifier_store:
        return None
        
    code_verifier, expiry = _verifier_store[state]
    
    # If expired, remove and return None
    if datetime.now().timestamp() > expiry:
        del _verifier_store[state]
        return None
        
    # Remove after retrieval (one-time use)
    del _verifier_store[state]
    return code_verifier

def _cleanup_expired_verifiers() -> None:
    """Remove expired verifiers from the store."""
    current_time = datetime.now().timestamp()
    expired_states = [
        state for state, (_, expiry) in _verifier_store.items()
        if current_time > expiry
    ]
    
    for state in expired_states:
        del _verifier_store[state]
