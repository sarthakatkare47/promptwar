import secrets
from typing import Any, Dict, Optional
from fastapi import Request
from fastapi.responses import JSONResponse
from fastapi.exceptions import RequestValidationError


class AppError(Exception):
    def __init__(
        self,
        code: str,
        message: str,
        status_code: int = 422,
        details: Optional[Dict[str, Any]] = None,
        headers: Optional[Dict[str, str]] = None,
    ):
        super().__init__(message)
        self.code = code
        self.message = message
        self.status_code = status_code
        self.details = details
        self.headers = headers or {}


def build_error_response(
    code: str,
    message: str,
    status_code: int = 422,
    details: Optional[Dict[str, Any]] = None,
    request_id: Optional[str] = None,
    headers: Optional[Dict[str, str]] = None,
) -> JSONResponse:
    if not request_id:
        request_id = f"req_{secrets.token_hex(6)}"
    
    error_obj: Dict[str, Any] = {
        "code": code,
        "message": message,
        "request_id": request_id,
    }
    if details is not None:
        error_obj["details"] = details
    
    response_headers = {
        "X-Request-ID": request_id,
        "X-Content-Type-Options": "nosniff",
        "Cache-Control": "no-store",
    }
    if headers:
        response_headers.update(headers)
        
    return JSONResponse(
        status_code=status_code,
        content={"error": error_obj},
        headers=response_headers,
    )


async def app_error_handler(request: Request, exc: AppError) -> JSONResponse:
    req_id = getattr(request.state, "request_id", None) or f"req_{secrets.token_hex(6)}"
    return build_error_response(
        code=exc.code,
        message=exc.message,
        status_code=exc.status_code,
        details=exc.details,
        request_id=req_id,
        headers=exc.headers,
    )


async def validation_error_handler(request: Request, exc: RequestValidationError) -> JSONResponse:
    req_id = getattr(request.state, "request_id", None) or f"req_{secrets.token_hex(6)}"
    errors = []
    for err in exc.errors():
        loc = ".".join(str(item) for item in err.get("loc", []))
        errors.append({
            "field": loc,
            "message": err.get("msg", "Invalid value"),
        })
    return build_error_response(
        code="VALIDATION_ERROR",
        message="Request validation failed.",
        status_code=422,
        details={"errors": errors},
        request_id=req_id,
    )


async def generic_exception_handler(request: Request, exc: Exception) -> JSONResponse:
    req_id = getattr(request.state, "request_id", None) or f"req_{secrets.token_hex(6)}"
    # Never expose internal exception details, file paths, or SQL in production error message
    return build_error_response(
        code="INTERNAL_ERROR",
        message="An unexpected internal server error occurred.",
        status_code=500,
        request_id=req_id,
    )
