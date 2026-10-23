import secrets
import time
from typing import Dict, List
from fastapi import Request
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import Response

from app.config import settings
from app.errors import build_error_response


class RequestContextMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next) -> Response:
        req_id = request.headers.get("X-Request-ID")
        if not req_id or not req_id.startswith("req_"):
            req_id = f"req_{secrets.token_hex(6)}"
        request.state.request_id = req_id

        # Security check: optional bearer token for /api/* routes
        if settings.IG_ACCESS_TOKEN and request.url.path.startswith("/api/"):
            auth_header = request.headers.get("Authorization", "")
            expected = f"Bearer {settings.IG_ACCESS_TOKEN}"
            if auth_header != expected:
                return build_error_response(
                    code="UNAUTHORIZED",
                    message="Valid bearer token is required.",
                    status_code=401,
                    request_id=req_id,
                )

        response: Response = await call_next(request)
        response.headers["X-Request-ID"] = req_id
        response.headers["X-Content-Type-Options"] = "nosniff"
        if request.url.path.startswith("/api/"):
            response.headers["Cache-Control"] = "no-store"
        return response


class InMemoryRateLimiter:
    """In-memory rate limiter for upload endpoints, tracking request timestamps per IP."""
    def __init__(self, limit_per_minute: int = 10):
        self.limit = limit_per_minute
        self.clients: Dict[str, List[float]] = {}

    def is_allowed(self, client_ip: str) -> bool:
        now = time.time()
        window_start = now - 60.0
        
        timestamps = self.clients.get(client_ip, [])
        # Discard timestamps older than 60 seconds
        valid = [t for t in timestamps if t > window_start]
        
        if len(valid) >= self.limit:
            self.clients[client_ip] = valid
            return False
            
        valid.append(now)
        self.clients[client_ip] = valid
        return True


upload_rate_limiter = InMemoryRateLimiter(settings.UPLOAD_RATE_LIMIT_PER_MINUTE)
