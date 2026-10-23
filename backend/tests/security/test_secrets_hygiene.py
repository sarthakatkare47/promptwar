import logging
import pytest
from app.config import settings
from app.logging_setup import SafeJsonFormatter


def test_health_endpoint_never_exposes_key(client):
    response = client.get("/health")
    assert response.status_code == 200
    data = response.json()
    assert "gemini_configured" in data
    assert isinstance(data["gemini_configured"], bool)
    raw_text = response.text
    key_val = settings.GEMINI_API_KEY.get_secret_value()
    if key_val:
        assert key_val not in raw_text


def test_logger_masks_secret_key():
    dummy_key = "AIzaSySecretFakeApiKey12345"
    formatter = SafeJsonFormatter(secrets_to_mask=(dummy_key,))

    record = logging.LogRecord(
        name="test_logger",
        level=logging.INFO,
        pathname="test.py",
        lineno=10,
        msg=f"Calling Gemini with key {dummy_key} now",
        args=(),
        exc_info=None,
    )
    formatted = formatter.format(record)
    assert dummy_key not in formatted
    assert "[REDACTED]" in formatted
