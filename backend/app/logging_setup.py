import json
import logging
import sys
from datetime import datetime, timezone
from typing import Any, Dict


class SafeJsonFormatter(logging.Formatter):
    def __init__(self, secrets_to_mask: tuple = ()):
        super().__init__()
        self.secrets = [s for s in secrets_to_mask if s]

    def format(self, record: logging.LogRecord) -> str:
        log_entry: Dict[str, Any] = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
        }

        # Include structured extra fields if provided
        for attr in ("request_id", "route", "status", "duration_ms", "invoice_id", "rule_ids", "error_code"):
            val = getattr(record, attr, None)
            if val is not None:
                log_entry[attr] = val

        if record.exc_info:
            log_entry["exception"] = self.formatException(record.exc_info)

        serialized = json.dumps(log_entry)
        for secret in self.secrets:
            if secret:
                serialized = serialized.replace(secret, "[REDACTED]")
        return serialized


def setup_logging(log_level: str = "INFO", secret_key: str = "") -> None:
    root = logging.getLogger()
    root.setLevel(log_level.upper())
    
    # Remove existing handlers to avoid duplicates
    for h in list(root.handlers):
        root.removeHandler(h)

    handler = logging.StreamHandler(sys.stdout)
    formatter = SafeJsonFormatter(secrets_to_mask=(secret_key,))
    handler.setFormatter(formatter)
    root.addHandler(handler)
