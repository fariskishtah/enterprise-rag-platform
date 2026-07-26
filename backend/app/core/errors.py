from typing import Any

from fastapi import Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException


class AppError(Exception):
    def __init__(self, *, status_code: int, code: str, message: str) -> None:
        super().__init__(message)
        self.status_code = status_code
        self.code = code
        self.message = message


class NotFoundError(AppError):
    def __init__(self, resource: str) -> None:
        super().__init__(
            status_code=404,
            code="resource_not_found",
            message=f"{resource} was not found.",
        )


class UploadValidationError(AppError):
    def __init__(self, *, code: str, message: str, status_code: int = 422) -> None:
        super().__init__(status_code=status_code, code=code, message=message)


class ConflictError(AppError):
    def __init__(self, *, code: str, message: str) -> None:
        super().__init__(status_code=409, code=code, message=message)


class ProcessingError(Exception):
    """Safe, user-facing failure raised by document and AI processing."""

    def __init__(self, message: str, *, code: str = "processing_failed") -> None:
        super().__init__(message)
        self.code = code
        self.message = message


class ModelProviderError(ProcessingError):
    def __init__(self, message: str) -> None:
        super().__init__(message, code="model_provider_unavailable")


class GenerationTimeoutError(ProcessingError):
    """Generation did not complete within the configured timeout."""

    def __init__(
        self,
        message: str = (
            "Generation timed out. The model may be overloaded — "
            "please retry with a simpler request."
        ),
    ) -> None:
        super().__init__(message, code="generation_timeout")


class GenerationQueueFullError(ProcessingError):
    """Too many generation requests are already queued."""

    def __init__(
        self,
        message: str = "The generation queue is full. Please wait and retry.",
    ) -> None:
        super().__init__(message, code="generation_queue_full")


def error_payload(code: str, message: str, details: Any | None = None) -> dict[str, Any]:
    error: dict[str, Any] = {"code": code, "message": message}
    if details is not None:
        error["details"] = details
    return {"error": error}


async def app_error_handler(_: Request, exc: AppError) -> JSONResponse:
    return JSONResponse(
        status_code=exc.status_code,
        content=error_payload(exc.code, exc.message),
    )


async def processing_error_handler(_: Request, exc: ProcessingError) -> JSONResponse:
    if isinstance(exc, GenerationTimeoutError):
        status_code = 504
    elif isinstance(exc, (ModelProviderError, GenerationQueueFullError)):
        status_code = 503
    else:
        status_code = 422
    return JSONResponse(
        status_code=status_code,
        content=error_payload(exc.code, exc.message),
    )


async def request_validation_handler(_: Request, exc: RequestValidationError) -> JSONResponse:
    details = [
        {"field": ".".join(str(part) for part in error["loc"]), "message": error["msg"]}
        for error in exc.errors()
    ]
    return JSONResponse(
        status_code=422,
        content=error_payload("request_validation_error", "The request is invalid.", details),
    )


async def http_error_handler(_: Request, exc: StarletteHTTPException) -> JSONResponse:
    message = exc.detail if isinstance(exc.detail, str) else "The request could not be completed."
    return JSONResponse(
        status_code=exc.status_code,
        content=error_payload("http_error", message),
        headers=exc.headers,
    )
