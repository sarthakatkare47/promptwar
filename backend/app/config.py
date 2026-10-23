from decimal import Decimal
from pathlib import Path
from typing import Optional, List
from pydantic import SecretStr, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=(".env", "backend/.env"),
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # Gemini API Settings
    GEMINI_API_KEY: SecretStr = SecretStr("")
    GEMINI_MODEL: str = "gemini-2.5-flash"
    EXTRACTOR: str = "gemini"  # "gemini" or "mock"
    GEMINI_TIMEOUT_SECONDS: int = 60
    GEMINI_MAX_RETRIES: int = 2

    # Cost Tracking (USD per million tokens)
    GEMINI_PRICE_INPUT_PER_MTOK_USD: Optional[float] = None
    GEMINI_PRICE_OUTPUT_PER_MTOK_USD: Optional[float] = None

    @field_validator("GEMINI_PRICE_INPUT_PER_MTOK_USD", "GEMINI_PRICE_OUTPUT_PER_MTOK_USD", mode="before")
    @classmethod
    def empty_str_to_none(cls, v):
        if v == "" or v is None:
            return None
        return float(v)

    # Quotas & Rate Limits
    DAILY_AI_CALL_LIMIT: int = 200
    UPLOAD_RATE_LIMIT_PER_MINUTE: int = 10

    # Upload Security Boundaries
    MAX_UPLOAD_BYTES: int = 10_485_760  # 10 MB
    MAX_PDF_PAGES: int = 5
    MAX_IMAGE_PIXELS: int = 40_000_000  # 40 Megapixels

    # Paths (resolved relative to backend directory or absolute)
    DATABASE_PATH: str = "data/invoiceguard.db"
    UPLOAD_DIR: str = "data/uploads"
    MOCK_FIXTURES_DIR: str = "benchmark/dataset/labels"

    # Security & Networking
    CORS_ORIGINS: str = "http://localhost:5173,http://127.0.0.1:5173"
    IG_ACCESS_TOKEN: str = ""
    LOG_LEVEL: str = "INFO"

    # Deterministic Rule Tolerances (using Decimal)
    AMOUNT_TOLERANCE_INR: Decimal = Decimal("1.00")
    CGST_SGST_TOLERANCE_INR: Decimal = Decimal("0.05")
    OLD_INVOICE_DAYS: int = 730

    @property
    def cors_origin_list(self) -> List[str]:
        return [origin.strip() for origin in self.CORS_ORIGINS.split(",") if origin.strip()]

    def get_database_path(self, base_dir: Optional[Path] = None) -> Path:
        p = Path(self.DATABASE_PATH)
        if p.is_absolute():
            return p
        root = base_dir or Path(__file__).resolve().parent.parent
        return root / p

    def get_upload_dir(self, base_dir: Optional[Path] = None) -> Path:
        p = Path(self.UPLOAD_DIR)
        if p.is_absolute():
            return p
        root = base_dir or Path(__file__).resolve().parent.parent
        return root / p


settings = Settings()
