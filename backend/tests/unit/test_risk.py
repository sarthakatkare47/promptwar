import pytest
from app.validation.risk import calculate_risk


def test_calculate_risk_clean():
    score, level, rec, breakdown = calculate_risk([])
    assert score == 0
    assert level == "low"
    assert rec == "no_issues_detected"
    assert len(breakdown) == 0


def test_calculate_risk_thresholds():
    # 10 pts -> low
    f_low = [{"rule_id": "EXT-002", "severity": "low"}]
    score, level, rec, _ = calculate_risk(f_low)
    assert score == 10 and level == "low" and rec == "no_issues_detected"

    # 20 pts (two low rules) -> medium
    f_two_low = [
        {"rule_id": "EXT-002", "severity": "low"},
        {"rule_id": "DATE-003", "severity": "low"},
    ]
    score, level, rec, _ = calculate_risk(f_two_low)
    assert score == 20 and level == "medium" and rec == "review_recommended"

    # 25 pts (one medium) -> medium
    f_med = [{"rule_id": "TAX-001", "severity": "medium"}]
    score, level, rec, _ = calculate_risk(f_med)
    assert score == 25 and level == "medium" and rec == "review_recommended"

    # 50 pts (one high) -> high
    f_high = [{"rule_id": "GST-002", "severity": "high"}]
    score, level, rec, _ = calculate_risk(f_high)
    assert score == 50 and level == "high" and rec == "high_priority_review"

    # Cap at 100
    f_huge = [
        {"rule_id": "GST-002", "severity": "high"},   # 50
        {"rule_id": "TAX-002", "severity": "high"},   # 50
        {"rule_id": "DUP-001", "severity": "high"},   # 50
    ]
    score, level, rec, breakdown = calculate_risk(f_huge)
    assert score == 100 and level == "high"
    assert len(breakdown) == 3


def test_calculate_risk_deduplicates_rule_id():
    # Same rule reported twice -> counts once at highest severity
    f_dup = [
        {"rule_id": "GST-001", "severity": "low"},
        {"rule_id": "GST-001", "severity": "high"},
    ]
    score, level, _, breakdown = calculate_risk(f_dup)
    assert score == 50
    assert len(breakdown) == 1
    assert breakdown[0]["points"] == 50
