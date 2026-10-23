from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware

from app.api.routes_health import router as health_router
from app.api.routes_invoices import router as invoices_router
from app.api.routes_reports import router as reports_router
from app.api.routes_scorecard import router as scorecard_router
from app.config import settings
from app.db.connection import get_connection, init_db
from app.db.repository import InvoiceRepository
from app.errors import (
    AppError,
    app_error_handler,
    generic_exception_handler,
    validation_error_handler,
)
from app.logging_setup import setup_logging
from app.security import RequestContextMiddleware


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup:
    setup_logging(
        log_level=settings.LOG_LEVEL,
        secret_key=settings.GEMINI_API_KEY.get_secret_value(),
    )
    init_db()
    with get_connection() as conn:
        recovered = InvoiceRepository.recover_interrupted_invoices(conn)
        if recovered > 0:
            import logging
            logging.getLogger("startup").info(f"Recovered {recovered} interrupted invoices to failed state.")
    settings.get_upload_dir().mkdir(parents=True, exist_ok=True)
    yield
    # Shutdown logic if any


def create_app() -> FastAPI:
    app = FastAPI(
        title="InvoiceGuard+ API",
        description="Deterministic screening and structured multimodal extraction for purchase invoices.",
        version="0.1.0",
        lifespan=lifespan,
    )

    # Security: CORS Allowlist
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origin_list,
        allow_credentials=True,
        allow_methods=["GET", "POST", "PATCH", "DELETE", "OPTIONS"],
        allow_headers=["*"],
    )

    # Security: Request Context, Token Auth, Nosniff Headers
    app.add_middleware(RequestContextMiddleware)

    # Error Handlers producing strict standard error format
    app.add_exception_handler(AppError, app_error_handler)
    app.add_exception_handler(RequestValidationError, validation_error_handler)
    app.add_exception_handler(Exception, generic_exception_handler)

    # Include Routers
    app.include_router(health_router)
    app.include_router(invoices_router)
    app.include_router(reports_router)
    app.include_router(scorecard_router)

    return app


app = create_app()
