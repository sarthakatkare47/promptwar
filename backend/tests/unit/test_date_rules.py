from datetime import date, timedelta
import pytest
from app.validation.dates import check_date_rules


def test_date_rules_clean():
    today = date(2025, 3, 15)
    findings = check_date_rules("2025-03-10", today=today)
    assert len(findings) == 0


def test_date_002_future_date():
    today = date(2025, 3, 15)
    findings = check_date_rules("2025-03-20", today=today)  # 5 days in future
    date002 = next((f for f in findings if f["rule_id"] == "DATE-002"), None)
    assert date002 is not None
    assert date002["severity"] == "medium"
    assert date002["evidence"]["days_in_future"] == 5


def test_date_003_old_invoice():
    today = date(2025, 3, 15)
    old_date = today - timedelta(days=735)  # 735 > 730
    findings = check_date_rules(old_date.isoformat(), today=today, old_invoice_days=730)
    date003 = next((f for f in findings if f["rule_id"] == "DATE-003"), None)
    assert date003 is not None
    assert date003["severity"] == "low"
    assert date003["evidence"]["age_days"] == 735
