"""Password hashing and the print agent key. Uses only the Python standard library."""
import hashlib
import hmac
import os
import secrets

from fastapi import Header, HTTPException

AGENT_KEY = os.environ.get("AGENT_KEY", "change-me-agent")
_ITERATIONS = 200_000


def hash_password(password: str) -> str:
    salt = secrets.token_hex(16)
    digest = hashlib.pbkdf2_hmac("sha256", password.encode(), bytes.fromhex(salt), _ITERATIONS).hex()
    return f"pbkdf2${_ITERATIONS}${salt}${digest}"


def verify_password(password: str, stored: str) -> bool:
    try:
        _, iterations, salt, digest = stored.split("$")
    except ValueError:
        return False
    check = hashlib.pbkdf2_hmac("sha256", password.encode(), bytes.fromhex(salt), int(iterations)).hex()
    return hmac.compare_digest(check, digest)


def require_agent(x_agent_key: str = Header(None)):
    """Only the print agent may post bills."""
    if not x_agent_key or not hmac.compare_digest(x_agent_key, AGENT_KEY):
        raise HTTPException(401, "Agent key is missing or wrong")
