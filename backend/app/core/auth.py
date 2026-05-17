import jwt
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from app.core.config import settings

# This scheme reads the "Authorization: Bearer <token>" header
bearer_scheme = HTTPBearer(auto_error=False)


def get_current_user(
    credentials: HTTPAuthorizationCredentials | None = Depends(bearer_scheme),
) -> dict:
    """
    FastAPI dependency that verifies the Supabase JWT token.

    - If a valid token is present, returns the decoded payload:
      { "sub": "<user_id>", "role": "authenticated" | "anon", "email": "..." }
    - If no token is provided, raises 401 Unauthorized.
    - If the token is invalid or expired, raises 401 Unauthorized.
    """
    if credentials is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Not authenticated. Please provide a valid Supabase token.",
            headers={"WWW-Authenticate": "Bearer"},
        )

    token = credentials.credentials
    secret = settings.SUPABASE_JWT_SECRET

    if not secret:
        # If no JWT secret is configured (e.g. local dev without .env),
        # fall back to decoding without verification so dev still works.
        try:
            payload = jwt.decode(token, options={"verify_signature": False})
            return payload
        except Exception:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid token format.",
            )

    try:
        payload = jwt.decode(
            token,
            secret,
            algorithms=["HS256"],
            options={"verify_aud": False},  # Supabase tokens use 'authenticated' as audience
        )
        return payload
    except jwt.ExpiredSignatureError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token has expired. Please sign in again.",
        )
    except jwt.InvalidTokenError as e:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=f"Invalid token: {str(e)}",
        )
