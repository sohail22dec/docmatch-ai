import jwt
import httpx
import threading
from jwt.algorithms import ECAlgorithm
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from app.core.config import settings

# This scheme reads the "Authorization: Bearer <token>" header
bearer_scheme = HTTPBearer(auto_error=False)

# ── JWKS cache ────────────────────────────────────────────────────────────────
# Supabase SDK v3+ issues ES256 tokens verified via their JWKS endpoint.
# We cache the public keys to avoid a round-trip on every request.

_jwks_cache: dict = {}      # kid → ECAlgorithm public key object
_jwks_lock = threading.Lock()

SUPABASE_JWKS_URL = f"{settings.SUPABASE_URL}/auth/v1/.well-known/jwks.json"


def _load_jwks() -> dict:
    """Fetch and cache JWKS from Supabase. Returns {kid: public_key}."""
    global _jwks_cache
    with _jwks_lock:
        if _jwks_cache:
            return _jwks_cache
        try:
            resp = httpx.get(SUPABASE_JWKS_URL, timeout=5)
            resp.raise_for_status()
            keys = resp.json().get("keys", [])
            for jwk in keys:
                kid = jwk.get("kid")
                if kid:
                    _jwks_cache[kid] = ECAlgorithm.from_jwk(jwk)
        except Exception as e:
            print(f"[auth] WARNING: Failed to fetch JWKS: {e}")
        return _jwks_cache


def _verify_token(token: str) -> dict:
    """
    Verify a Supabase JWT.

    Strategy:
    1. Peek at the token header to determine algorithm + kid.
    2. ES256  → look up the public key from Supabase JWKS and verify.
    3. HS256  → verify with SUPABASE_JWT_SECRET (legacy / older Supabase).
    4. No secret configured → decode without signature verification (dev fallback).
    """
    try:
        header = jwt.get_unverified_header(token)
    except jwt.DecodeError as e:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=f"Invalid token format: {e}",
        )

    alg = header.get("alg", "")
    kid = header.get("kid")

    # ── ES256: verify with Supabase public key ────────────────────────────────
    if alg == "ES256":
        jwks = _load_jwks()
        public_key = jwks.get(kid) if kid else (next(iter(jwks.values()), None))

        if public_key is None:
            # Refresh cache once and retry
            global _jwks_cache
            with _jwks_lock:
                _jwks_cache = {}
            jwks = _load_jwks()
            public_key = jwks.get(kid) if kid else (next(iter(jwks.values()), None))

        if public_key is None:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Unable to locate Supabase public key for token verification.",
            )

        try:
            return jwt.decode(
                token,
                public_key,
                algorithms=["ES256"],
                options={"verify_aud": False},
            )
        except jwt.ExpiredSignatureError:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Token has expired. Please sign in again.",
            )
        except jwt.InvalidTokenError as e:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail=f"Invalid token: {e}",
            )

    # ── HS256: legacy Supabase tokens signed with JWT secret ──────────────────
    if alg == "HS256":
        secret = settings.SUPABASE_JWT_SECRET
        if not secret:
            # Dev fallback: decode without verification
            try:
                return jwt.decode(token, options={"verify_signature": False})
            except Exception:
                raise HTTPException(
                    status_code=status.HTTP_401_UNAUTHORIZED,
                    detail="Invalid token format.",
                )
        try:
            return jwt.decode(
                token,
                secret,
                algorithms=["HS256"],
                options={"verify_aud": False},
            )
        except jwt.ExpiredSignatureError:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Token has expired. Please sign in again.",
            )
        except jwt.InvalidTokenError as e:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail=f"Invalid token: {e}",
            )

    # ── Unknown algorithm ─────────────────────────────────────────────────────
    raise HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail=f"Unsupported token algorithm: {alg}",
    )


def get_current_user(
    credentials: HTTPAuthorizationCredentials | None = Depends(bearer_scheme),
) -> dict:
    """
    FastAPI dependency that verifies the Supabase JWT token.

    Supports both ES256 (Supabase SDK v3+) and HS256 (legacy) tokens.
    Returns the decoded payload: { "sub": "<user_id>", "role": "authenticated" | "anon", ... }
    Raises 401 if no token is provided or if validation fails.
    """
    if credentials is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Not authenticated. Please provide a valid Supabase token.",
            headers={"WWW-Authenticate": "Bearer"},
        )

    return _verify_token(credentials.credentials)
