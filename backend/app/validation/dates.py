import secrets
from datetime import date, datetime, timedelta, timezone
from typing import Any, Dict, List, Optional
from app.validation.rules_config import DEFAULT_OLD_INVOICE_DAYS

# IST Timezone: UTC+05:30
IST = timezone(timedelta(hours=5, minutes=30))


def get_current_ist_date() -> date:
    return datetime.now(IST).date()


def parse_iso_date(val: Optional[str]) -> Optional[date]:
    if not val:
        return None
    try:
        return date.fromisoformat(str(val).strip())
    except (ValueError, TypeError):
        return None


def check_date_rules(
    invoice_date_raw: Optional[str],
    today: Optional[date] = None,
    old_invoice_days: int = DEFAULT_OLD_INVOICE_DAYS,
) -> List[Dict[str, Any]]:
    findings = []
    inv_date = parse_iso_date(invoice_date_raw)
    if not inv_date:
        return findings

    ref_today = today or get_current_ist_date()

    # DATE-002: Future date
    if inv_date > ref_today:
        days_ahead = (inv_date - ref_today).days
        findings.append({
            "finding_id": f"fnd_{secrets.token_hex(6)}",
            "rule_id": "DATE-002",
            "severity": "medium",
            "category": "date",
            "title": "Invoice date is in the future",
            "explanation": "The extracted invoice date is later than today's date in Indian Standard Time (UTC+05:30). Check for post-dated billing or an OCR/extraction error.",
            "evidence": {
                "invoice_date": inv_date.isoformat(),
                "today": ref_today.isoformat(),
                "days_in_future": days_ahead,
            },
        })

    # DATE-003: Very old invoice (> 730 days)
    age_days = (ref_today - inv_date).days
    if age_days > old_invoice_days:
        findings.append({
            "finding_id": f"fnd_{secrets.token_hex(6)}",
            "rule_id": "DATE-003",
            "severity": "low",
            "category": "date",
            "title": "Invoice date is unusually old",
            "explanation": f"The invoice date is more than {old_invoice_days} days in the past. Legitimate late invoicing occurs, but this document should be verified.",
            "evidence": {
                "invoice_date": inv_date.isoformat(),
                "age_days": age_days,
                "threshold_days": old_invoice_days,
            },
        })

    return findings
