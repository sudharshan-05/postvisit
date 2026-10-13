"""
PostVisit AI - Input Guardrails
Validates uploaded consultation files before any heavy AI/ASR pipeline begins.
Enforces file format, size limits, readability, and container integrity.
"""

import os
import mimetypes
from pathlib import Path
from typing import Optional, Set
from src.guardrails.base import GuardrailResult

ALLOWED_EXTENSIONS: Set[str] = {".mp3", ".mp4", ".wav", ".m4a", ".flac", ".ogg", ".webm", ".aac"}
DEFAULT_MAX_SIZE_MB = 100


class InputGuardrail:
    """
    Validates input file existence, format, size, and readability.
    Rejects invalid inputs safely without crashing background workers.
    """

    def __init__(
        self,
        allowed_extensions: Optional[Set[str]] = None,
        max_upload_size_mb: int = DEFAULT_MAX_SIZE_MB
    ):
        self.allowed_extensions = {ext.lower() for ext in (allowed_extensions or ALLOWED_EXTENSIONS)}
        self.max_size_bytes = max_upload_size_mb * 1024 * 1024

    def validate(
        self,
        file_path: str,
        filename: Optional[str] = None,
        mime_type: Optional[str] = None
    ) -> GuardrailResult:
        """
        Validates the consultation file before processing.
        """
        effective_name = filename or Path(file_path).name
        if not effective_name or not effective_name.strip():
            return GuardrailResult(
                passed=False,
                action="FAILED",
                error_code="INVALID_FILENAME",
                message="A valid filename must be provided."
            )

        # 1. Check Extension
        ext = Path(effective_name).suffix.lower()
        if ext not in self.allowed_extensions:
            return GuardrailResult(
                passed=False,
                action="FAILED",
                error_code="UNSUPPORTED_MEDIA_TYPE",
                message=(
                    f"Unsupported file format '{ext}'. "
                    f"Allowed formats: {', '.join(sorted(self.allowed_extensions))}."
                ),
                details={"extension": ext}
            )

        # 2. Check File Existence
        path_obj = Path(file_path)
        if not path_obj.exists():
            return GuardrailResult(
                passed=False,
                action="FAILED",
                error_code="FILE_NOT_FOUND",
                message=f"Uploaded file not found at path: {file_path}"
            )

        # 3. Check File Size
        try:
            file_size = path_obj.stat().st_size
        except Exception as e:
            return GuardrailResult(
                passed=False,
                action="FAILED",
                error_code="FILE_READ_ERROR",
                message=f"Failed to access file metadata: {e}"
            )

        if file_size == 0:
            return GuardrailResult(
                passed=False,
                action="FAILED",
                error_code="EMPTY_FILE",
                message="Uploaded file is empty (0 bytes)."
            )

        if file_size > self.max_size_bytes:
            return GuardrailResult(
                passed=False,
                action="FAILED",
                error_code="FILE_TOO_LARGE",
                message=f"File size ({round(file_size / (1024*1024), 2)} MB) exceeds maximum allowed limit.",
                details={"file_size_bytes": file_size, "max_size_bytes": self.max_size_bytes}
            )

        # 4. Check Container Header / Readability
        try:
            with open(path_obj, "rb") as f:
                header = f.read(64)
                if len(header) < 4:
                    return GuardrailResult(
                        passed=False,
                        action="FAILED",
                        error_code="CORRUPTED_FILE",
                        message="File header is truncated or unreadable."
                    )
        except Exception as e:
            return GuardrailResult(
                passed=False,
                action="FAILED",
                error_code="FILE_READ_ERROR",
                message=f"File could not be opened for reading: {e}"
            )

        return GuardrailResult(
            passed=True,
            action="CONTINUE",
            message="Input guardrail passed.",
            details={"filename": effective_name, "file_size_bytes": file_size, "extension": ext}
        )
