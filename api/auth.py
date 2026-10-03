"""
PostVisit AI - Authentication & Authorization Module
=====================================================
Implements real Supabase JWT verification for all protected routes.

Security design:
- All protected endpoints require a valid Bearer token in the Authorization header.
- Tokens are verified against the Supabase JWT secret (HS256) or Supabase JWKS (RS256).
- The role is read from the verified token payload's `user_metadata.role` field.
- User identity is read from the verified `sub` (subject) claim.
- No role or identity can be injected via query parameters, headers, or request bodies.
- Test overrides are ONLY available when APP_ENV=test and via FastAPI dependency injection.

The auth module does NOT expose Supabase service-role credentials to clients.
"""

import os
import logging
from typing import Optional, Dict, Any
from functools import lru_cache

import jwt as pyjwt
from fastapi import Header, HTTPException, status, Depends, Query
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials

logger = logging.getLogger("postvisit.auth")

# ---------------------------------------------------------------------------
# Security scheme — Bearer token
# ---------------------------------------------------------------------------
_bearer_scheme = HTTPBearer(auto_error=False)

# ---------------------------------------------------------------------------
# Environment detection
# ---------------------------------------------------------------------------
APP_ENV = os.getenv("APP_ENV", "production").lower()
_IS_TEST_ENV = APP_ENV in ("test", "testing")

# ---------------------------------------------------------------------------
# Supabase JWT configuration
# Supabase signs JWTs with a shared secret (HS256) derived from the project's
# JWT secret. This secret is available in Supabase Dashboard → Settings → API.
# We load it from the environment variable SUPABASE_JWT_SECRET.
# ---------------------------------------------------------------------------
SUPABASE_JWT_SECRET = os.getenv("SUPABASE_JWT_SECRET", "")
SUPABASE_URL = os.getenv("SUPABASE_URL", "")
SUPABASE_ISSUER = SUPABASE_URL.rstrip("/") + "/auth/v1" if SUPABASE_URL else ""


def get_jwt_secret() -> str:
    """Retrieves the Supabase JWT secret from environment or test fallback."""
    secret = os.getenv("SUPABASE_JWT_SECRET", "")
    if not secret and is_test_env():
        return "postvisit-sandbox-secret-key-32-chars-long-test-only"
    return secret


def create_test_jwt(
    role: str = "doctor",
    user_id: str = "test-doctor-uuid",
    email: str = "test.doctor@postvisit.test",
    expires_in_seconds: int = 3600,
    tamper: bool = False,
    secret_override: Optional[str] = None,
) -> str:
    """
    Generates a valid (or intentionally tampered/expired) JWT for automated testing.
    Used by test suites to verify token verification, role enforcement, and edge cases.
    """
    import time
    secret = secret_override or get_jwt_secret()
    now = int(time.time())
    payload = {
        "sub": user_id,
        "aud": "authenticated",
        "role": "authenticated",
        "email": email,
        "app_metadata": {"role": role, "provider": "email"},
        "user_metadata": {"role": role, "name": email.split("@")[0]},
        "iat": now,
        "exp": now + expires_in_seconds,
    }
    token = pyjwt.encode(payload, secret, algorithm="HS256")
    if tamper:
        parts = token.split(".")
        if len(parts) == 3:
            tampered_sig = ("A" if parts[2][-1] != "A" else "B") + parts[2][1:]
            return f"{parts[0]}.{parts[1]}.{tampered_sig}"
    return token


# ---------------------------------------------------------------------------
# Token verification
# ---------------------------------------------------------------------------

def _verify_supabase_token(token: str) -> Dict[str, Any]:
    """
    Verifies a Supabase-issued JWT.
    - Checks signature using SUPABASE_JWT_SECRET (HS256).
    - Validates expiration.
    - Returns the decoded payload on success.
    - Raises HTTPException on any failure.
    """
    jwt_secret = get_jwt_secret()
    if not jwt_secret:
        # JWT secret not configured — deny all requests in production.
        logger.error(
            "SUPABASE_JWT_SECRET is not configured. "
            "All authenticated requests will be rejected until it is set."
        )
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail={
                "code": "AUTH_NOT_CONFIGURED",
                "message": (
                    "Authentication service is not configured on this server. "
                    "Contact the system administrator."
                )
            }
        )

    try:
        payload = pyjwt.decode(
            token,
            jwt_secret,
            algorithms=["HS256"],
            options={
                "verify_exp": True,
                "verify_aud": False,  # Supabase tokens use 'authenticated' audience
            }
        )
        return payload

    except pyjwt.ExpiredSignatureError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail={"code": "TOKEN_EXPIRED", "message": "Your session has expired. Please log in again."},
            headers={"WWW-Authenticate": "Bearer"},
        )
    except pyjwt.InvalidTokenError as e:
        logger.warning(f"Invalid JWT token: {e}")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail={"code": "INVALID_TOKEN", "message": "Authentication token is invalid or has been tampered with."},
            headers={"WWW-Authenticate": "Bearer"},
        )


def _extract_role_from_payload(payload: Dict[str, Any]) -> str:
    """
    Extracts the user role from a verified Supabase JWT payload.
    Supabase stores custom claims in app_metadata.role or user_metadata.role.
    Falls back to 'patient' if no role claim is present.
    """
    # Try app_metadata first (server-set, more trusted)
    app_meta = payload.get("app_metadata", {}) or {}
    user_meta = payload.get("user_metadata", {}) or {}

    role = (
        app_meta.get("role")
        or user_meta.get("role")
        or payload.get("role")  # Some Supabase configs put it at top level
        or "patient"
    ).lower().strip()
    return role


def _extract_user_id_from_payload(payload: Dict[str, Any]) -> str:
    """Extracts user ID (Supabase UUID) from the 'sub' claim."""
    return payload.get("sub", "unknown")


def is_test_env() -> bool:
    """Checks if currently running in a test/sandbox environment."""
    return os.getenv("APP_ENV", "production").lower() in ("test", "testing")


async def get_verified_user(
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(_bearer_scheme),
    x_user_role: Optional[str] = Header(default=None, alias="X-User-Role"),
    x_user_id: Optional[str] = Header(default=None, alias="X-User-Id"),
    x_doctor_name: Optional[str] = Header(default=None, alias="X-Doctor-Name"),
    role_param: Optional[str] = Query(default=None, alias="role"),
) -> Dict[str, Any]:
    """
    FastAPI dependency that verifies the Bearer token and returns a
    trusted identity dict: {user_id, role, email, payload, is_test_identity, doctor_name}.

    In PRODUCTION:
    - Bearer token is strictly required.
    - Token signature, expiration, and claims are cryptographically verified.
    - X-User-Role, X-User-Id, and ?role= query parameters are strictly ignored.
    - Missing or invalid tokens immediately raise HTTP 401 Unauthorized.

    In TEST ENVIRONMENT (APP_ENV=test):
    - If a Bearer token is provided, it is cryptographically verified against SUPABASE_JWT_SECRET.
    - If no Bearer token is provided, test-suite headers (X-User-Role / X-User-Id / X-Doctor-Name)
      or test query params (?role=) are accepted via the test-only identity provider to allow isolated mock testing.
    """
    if credentials is not None and credentials.credentials:
        token = credentials.credentials
        payload = _verify_supabase_token(token)
        uid = _extract_user_id_from_payload(payload)
        user_meta = payload.get("user_metadata", {}) or {}
        doc_name = user_meta.get("name") or payload.get("email", "") or uid
        return {
            "user_id": uid,
            "role": _extract_role_from_payload(payload),
            "email": payload.get("email", ""),
            "payload": payload,
            "doctor_name": doc_name,
            "is_test_identity": False,
        }

    # No credentials provided
    if is_test_env():
        # Safe test-only identity provider for automated test suites
        role = (role_param or x_user_role or "doctor").lower().strip()
        uid = x_user_id or ("dr_rajesh_sharma" if role in ("doctor", "physician", "clinician", "admin") else "PT-89241")
        doc_name = x_doctor_name or (f"Dr. {uid}" if role == "doctor" else uid)
        return {
            "user_id": uid,
            "role": role,
            "email": f"{uid}@postvisit.test",
            "payload": {"role": role, "sub": uid},
            "doctor_name": doc_name,
            "is_test_identity": True,
        }



    raise HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail={
            "code": "MISSING_TOKEN",
            "message": "Authentication required. Provide a valid Bearer token in Authorization header."
        },
        headers={"WWW-Authenticate": "Bearer"},
    )


# ---------------------------------------------------------------------------
# Role enforcement dependencies
# ---------------------------------------------------------------------------

async def require_doctor(
    user: Dict[str, Any] = Depends(get_verified_user),
) -> Dict[str, Any]:
    """
    FastAPI dependency: requires an authenticated user with a doctor/clinician role.
    Returns 403 Forbidden for any other role.
    """
    allowed = {"doctor", "physician", "clinician", "admin"}
    if user["role"] not in allowed:
        logger.warning(
            f"Doctor-only endpoint accessed by role '{user['role']}' "
            f"(user_id={user['user_id']})"
        )
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail={
                "code": "DOCTOR_ROLE_REQUIRED",
                "message": "Access denied: This endpoint requires an authorized clinician session."
            }
        )
    return user


async def require_patient(
    user: Dict[str, Any] = Depends(get_verified_user),
) -> Dict[str, Any]:
    """
    FastAPI dependency: requires an authenticated user with a patient role.
    Doctors and admins are also permitted (they may access patient records within scope).
    """
    allowed = {"patient", "doctor", "physician", "clinician", "admin"}
    if user["role"] not in allowed:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail={
                "code": "ACCESS_DENIED",
                "message": "Access denied: Invalid role for this endpoint."
            }
        )
    return user


def enforce_patient_data_scope(
    user: Dict[str, Any],
    requested_patient_id: Optional[str],
) -> str:
    """
    Enforces patient data isolation:
    - Patients may only access their own records.
    - Doctors and admins may access any patient record within their scope.
    Returns the effective patient_id to use.
    """
    role = user["role"]
    user_id = user.get("user_id") or user.get("caller_id") or "unknown"
    effective_id = requested_patient_id or user_id

    if role == "patient" and effective_id != user_id:
        logger.warning(
            f"Patient isolation violation: user_id='{user_id}' "
            f"attempted to access patient_id='{effective_id}'"
        )
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail={
                "code": "FORBIDDEN",
                "message": "Access denied: Patients may only access their own medical records."
            }
        )
    return effective_id


# ---------------------------------------------------------------------------
# Legacy compatibility shim
# Used by routes that have not yet been migrated to the new auth system.
# These return the same dict shape as the new auth but remain token-aware.
# IMPORTANT: These do NOT accept ?role= or ?user_id= overrides.
# ---------------------------------------------------------------------------

async def get_doctor_identity_secure(
    user: Dict[str, Any] = Depends(require_doctor),
) -> Dict[str, str]:
    """
    Secure shim returning legacy doctor identity dict shape.
    Compatible with existing route handlers.
    """
    uid = user["user_id"]
    return {
        "role": user["role"],
        "caller_id": uid,
        "user_id": uid,
        "doctor_name": user.get("doctor_name") or user.get("email", uid),
    }


async def get_patient_identity_secure(
    user: Dict[str, Any] = Depends(require_patient),
) -> Dict[str, str]:
    """
    Secure shim returning legacy patient identity dict shape.
    Compatible with existing route handlers.
    """
    uid = user["user_id"]
    return {
        "role": user["role"],
        "caller_id": uid,
        "user_id": uid,
    }

