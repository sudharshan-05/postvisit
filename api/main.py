"""
PostVisit AI - FastAPI Application Entry Point
Exposes RESTful endpoints for health checks, API metadata, and clinical consultation processing.
"""

import os
import sys
import logging
from pathlib import Path
from contextlib import asynccontextmanager

from typing import Optional
from fastapi import FastAPI, Request, status, Query, Depends
from fastapi.responses import JSONResponse, FileResponse
from fastapi.staticfiles import StaticFiles
from fastapi.exceptions import RequestValidationError
from starlette.exceptions import HTTPException as StarletteHTTPException
from fastapi.middleware.cors import CORSMiddleware

PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from api.config import get_settings
from api.schemas.consultation import HealthResponse, RootResponse, ErrorResponse
from api.routes.consultations import router as consultations_router
from api.routes.summaries import router as summaries_router
from api.routes.guidelines import router as guidelines_router
from api.routes.patient import router as patient_router
from api.routes.doctor import router as doctor_router
from api.auth import get_verified_user

# Setup top-level application logger
logging.basicConfig(
    level=logging.INFO,
    format="[%(asctime)s] %(levelname)s [%(name)s] %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S"
)
logger = logging.getLogger("postvisit.api")

settings = get_settings()


@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    Application lifecycle manager.
    Logs startup configuration and initializes background worker with crash recovery.
    """
    logger.info("=" * 60)
    logger.info(f"Starting {settings.PROJECT_NAME} API v{settings.VERSION}")
    logger.info(f"Max Upload Size: {settings.MAX_UPLOAD_SIZE_MB} MB")
    logger.info(f"Allowed Media: {', '.join(sorted(settings.ALLOWED_EXTENSIONS))}")
    logger.info("=" * 60)

    from src.workflow.worker import get_background_worker
    worker = get_background_worker()
    worker.startup()

    yield
    logger.info("Shutting down PostVisit AI API...")
    worker.shutdown()


app = FastAPI(
    title=settings.PROJECT_NAME,
    description=settings.DESCRIPTION,
    version=settings.VERSION,
    docs_url="/docs",
    redoc_url="/redoc",
    openapi_url="/openapi.json",
    lifespan=lifespan
)

# Enable CORS — environment-specific allowed origins
# In production: set CORS_ALLOWED_ORIGINS to a comma-separated list of trusted frontend URLs.
# In development: defaults to localhost for safety.
_raw_origins = os.getenv("CORS_ALLOWED_ORIGINS", "http://localhost:3000,http://127.0.0.1:3000,http://localhost:8000,http://127.0.0.1:8000")
_allowed_origins = [o.strip() for o in _raw_origins.split(",") if o.strip()]

app.add_middleware(
    CORSMiddleware,
    allow_origins=_allowed_origins,
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS"],
    allow_headers=["Authorization", "Content-Type", "X-User-Role", "X-User-Id", "X-Doctor-Name"],
)


@app.get(
    "/health",
    response_model=HealthResponse,
    status_code=status.HTTP_200_OK,
    tags=["System"],
    summary="Service Health Check",
    description="Rapid health check endpoint. Does NOT load ML models or trigger the AI pipeline."
)
async def health_check():
    return HealthResponse(
        status="ok",
        service="PostVisit AI API",
        version=settings.VERSION
    )


@app.get(
    "/",
    response_model=RootResponse,
    status_code=status.HTTP_200_OK,
    tags=["System"],
    summary="API Root Information",
    description="Returns high-level metadata, documentation links, and service version."
)
async def root():
    return RootResponse(
        name=settings.PROJECT_NAME,
        description=settings.DESCRIPTION,
        version=settings.VERSION,
        docs="/docs",
        health="/health"
    )


# Include domain routers
app.include_router(consultations_router)
app.include_router(summaries_router)
app.include_router(guidelines_router)
app.include_router(patient_router)
app.include_router(doctor_router)


# Authentication & Session Profile Endpoint
@app.get(
    "/api/v1/auth/me",
    tags=["Authentication"],
    summary="Get Active User Session Profile",
    description=(
        "Returns authenticated session details from a verified Supabase Bearer token. "
        "Requires Authorization: Bearer <token>. "
        "In test environments (APP_ENV=test), returns a test identity when no token is provided."
    )
)
async def get_current_user_profile(
    user: dict = Depends(get_verified_user)
):
    """
    Returns the verified user's identity from their Supabase JWT.
    Does NOT accept ?role= query parameter overrides.
    """
    role = user["role"]
    user_id = user["user_id"]
    email = user.get("email", "")
    is_test = user.get("is_test_identity", False)

    if role in ("doctor", "physician", "clinician", "admin"):
        return {
            "user_id": user_id,
            "name": email or "Authenticated Doctor",
            "role": "doctor",
            "permissions": [
                "consultations:read",
                "consultations:write",
                "summaries:generate",
                "summaries:approve",
                "summaries:amend",
                "guidelines:cross_reference",
                "guidelines:review"
            ],
            "is_test_identity": is_test
        }
    return {
        "user_id": user_id,
        "name": email or "Authenticated Patient",
        "role": "patient",
        "patient_id": user_id,
        "permissions": [
            "summaries:read_approved",
            "patient_portal:access",
            "lab_reports:upload",
            "recovery_plan:track",
            "chat:inquire",
            "voice:record"
        ],
        "is_test_identity": is_test
    }


# Dashboard UI Views
STATIC_DIR = PROJECT_ROOT / "static"
if STATIC_DIR.exists():
    app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")

    @app.get("/app", response_class=FileResponse, tags=["Dashboard"], include_in_schema=False)
    @app.get("/dashboard", response_class=FileResponse, tags=["Dashboard"], include_in_schema=False)
    async def serve_dashboard():
        index_file = STATIC_DIR / "index.html"
        return FileResponse(str(index_file))


# Custom global exception handlers for standardized error schema
@app.exception_handler(StarletteHTTPException)
async def http_exception_handler(request: Request, exc: StarletteHTTPException):
    code_map = {
        400: "BAD_REQUEST",
        401: "UNAUTHORIZED",
        403: "FORBIDDEN",
        404: "NOT_FOUND",
        405: "METHOD_NOT_ALLOWED",
        413: "FILE_TOO_LARGE",
        415: "UNSUPPORTED_MEDIA_TYPE",
        500: "INTERNAL_SERVER_ERROR"
    }
    error_code = code_map.get(exc.status_code, "HTTP_ERROR")
    if isinstance(exc.detail, dict):
        error_code = exc.detail.get("code", error_code)
        msg = exc.detail.get("message", str(exc.detail))
    else:
        msg = str(exc.detail)

    return JSONResponse(
        status_code=exc.status_code,
        content={
            "error": {
                "code": error_code,
                "message": msg
            },
            "detail": exc.detail
        }
    )


@app.exception_handler(RequestValidationError)
async def validation_exception_handler(request: Request, exc: RequestValidationError):
    return JSONResponse(
        status_code=status.HTTP_400_BAD_REQUEST,
        content={
            "error": {
                "code": "VALIDATION_ERROR",
                "message": "Invalid request parameters or payload format."
            }
        }
    )


@app.exception_handler(Exception)
async def unhandled_exception_handler(request: Request, exc: Exception):
    logger.error(f"Unhandled exception during request processing: {str(exc)}", exc_info=True)
    return JSONResponse(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        content={
            "error": {
                "code": "INTERNAL_SERVER_ERROR",
                "message": "An unexpected error occurred while processing the request."
            }
        }
    )
