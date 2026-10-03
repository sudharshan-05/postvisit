"""
PostVisit AI - FastAPI Application Entry Point
Exposes RESTful endpoints for health checks, API metadata, and clinical consultation processing.
"""

import sys
import logging
from pathlib import Path
from contextlib import asynccontextmanager

from typing import Optional
from fastapi import FastAPI, Request, status, Query
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

# Enable CORS for future frontend integration
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
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
    description="Returns authenticated session details, user role, and permissions."
)
async def get_current_user_profile(
    role: Optional[str] = Query(default=None),
    user_id: Optional[str] = Query(default=None)
):
    current_role = (role or "doctor").lower()
    if current_role in ("doctor", "physician", "system"):
        return {
            "user_id": user_id or "dr_rajesh_sharma",
            "name": "Dr. Rajesh Sharma, MD",
            "role": "doctor",
            "license": "TN-MC-84920",
            "department": "Internal Medicine",
            "permissions": [
                "consultations:read",
                "consultations:write",
                "summaries:generate",
                "summaries:approve",
                "summaries:amend",
                "guidelines:cross_reference",
                "guidelines:review"
            ]
        }
    return {
        "user_id": user_id or "pt_ananya_patel",
        "name": "Ananya Patel",
        "role": "patient",
        "patient_id": "PT-89241",
        "permissions": [
            "summaries:read_approved",
            "patient_portal:access",
            "lab_reports:upload",
            "recovery_plan:track",
            "chat:inquire",
            "voice:record"
        ]
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
