from dataclasses import dataclass
from typing import Optional, Protocol
from app.schemas.extraction import ExtractionResult


class ExtractionError(Exception):
    def __init__(self, code: str, message: str, retryable: bool = False):
        super().__init__(message)
        self.code = code
        self.message = message
        self.retryable = retryable


@dataclass
class ExtractorOutput:
    result: ExtractionResult
    model: str
    latency_ms: int
    input_tokens: Optional[int] = None
    output_tokens: Optional[int] = None


class Extractor(Protocol):
    async def extract(self, file_bytes: bytes, mime_type: str) -> ExtractorOutput:
        ...
