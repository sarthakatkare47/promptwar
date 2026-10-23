import asyncio
import time
from typing import Optional
from google import genai
from google.genai import types
from google.genai.errors import APIError

from app.config import settings
from app.extraction.base import ExtractionError, ExtractorOutput
from app.extraction.prompts import INVOICE_EXTRACTION_SYSTEM_INSTRUCTION
from app.schemas.extraction import ExtractionResult


class GeminiExtractor:
    def __init__(self, api_key: Optional[str] = None, model: Optional[str] = None):
        key = api_key or settings.GEMINI_API_KEY.get_secret_value()
        self.api_key = key
        self.model_name = model or settings.GEMINI_MODEL

    async def extract(self, file_bytes: bytes, mime_type: str) -> ExtractorOutput:
        if not self.api_key:
            raise ExtractionError(
                code="AI_NOT_CONFIGURED",
                message="GEMINI_API_KEY is not configured in backend/.env.",
                retryable=False,
            )

        client = genai.Client(api_key=self.api_key)
        part = types.Part.from_bytes(data=file_bytes, mime_type=mime_type)

        config = types.GenerateContentConfig(
            system_instruction=INVOICE_EXTRACTION_SYSTEM_INSTRUCTION,
            temperature=0.0,
            response_mime_type="application/json",
            response_schema=ExtractionResult,
        )

        max_retries = settings.GEMINI_MAX_RETRIES
        timeout = settings.GEMINI_TIMEOUT_SECONDS

        start_time = time.perf_counter()
        last_error = None

        for attempt in range(max_retries + 1):
            try:
                # Call Gemini API in threadpool with timeout
                response = await asyncio.wait_for(
                    asyncio.to_thread(
                        client.models.generate_content,
                        model=self.model_name,
                        contents=[part, "Extract the structured invoice fields from this document."],
                        config=config,
                    ),
                    timeout=float(timeout),
                )

                latency_ms = int((time.perf_counter() - start_time) * 1000)

                # Extract token usage if available
                input_tokens = None
                output_tokens = None
                if hasattr(response, "usage_metadata") and response.usage_metadata:
                    input_tokens = getattr(response.usage_metadata, "prompt_token_count", None)
                    output_tokens = getattr(response.usage_metadata, "candidates_token_count", None)

                # Parse and validate response JSON text
                text = getattr(response, "text", None)
                if not text:
                    raise ExtractionError("AI_BAD_OUTPUT", "Model returned an empty text response.", retryable=False)

                try:
                    result = ExtractionResult.model_validate_json(text)
                except Exception as ve:
                    raise ExtractionError("AI_BAD_OUTPUT", f"Model response failed schema validation: {ve}", retryable=False)

                return ExtractorOutput(
                    result=result,
                    model=self.model_name,
                    latency_ms=latency_ms,
                    input_tokens=input_tokens,
                    output_tokens=output_tokens,
                )

            except asyncio.TimeoutError:
                last_error = ExtractionError("AI_TIMEOUT", f"Gemini extraction timed out after {timeout} seconds.", retryable=True)
            except APIError as e:
                code_str = str(e)
                status_code = getattr(e, "code", None)
                if status_code == 429 or "429" in code_str or "RESOURCE_EXHAUSTED" in code_str:
                    last_error = ExtractionError("AI_RATE_LIMITED", "Gemini API rate limit exceeded.", retryable=True)
                elif status_code in (401, 403) or "401" in code_str or "403" in code_str:
                    last_error = ExtractionError("AI_NOT_CONFIGURED", "Gemini API key is invalid or unauthorized.", retryable=False)
                    break
                elif status_code and status_code >= 500:
                    last_error = ExtractionError("AI_UNAVAILABLE", "Gemini API service temporarily unavailable.", retryable=True)
                else:
                    last_error = ExtractionError("AI_UNAVAILABLE", f"Gemini API error: {e}", retryable=True)
            except ExtractionError:
                raise
            except Exception as e:
                last_error = ExtractionError("AI_UNAVAILABLE", f"Unexpected extraction error: {e}", retryable=True)

            if attempt < max_retries and last_error and last_error.retryable:
                await asyncio.sleep(2 ** attempt)  # Exponential backoff (1s, 2s...)
            else:
                break

        if last_error:
            raise last_error
        raise ExtractionError("AI_UNAVAILABLE", "Extraction failed with unknown error.")
