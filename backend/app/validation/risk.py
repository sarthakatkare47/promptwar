from typing import Any, Dict, List, Tuple
from app.validation.rules_config import SEVERITY_POINTS


def calculate_risk(findings: List[Dict[str, Any]]) -> Tuple[int, str, str, List[Dict[str, Any]]]:
    """
    Computes transparent risk score, risk level, recommendation, and itemized breakdown.
    Each unique rule ID contributes once at its highest severity.
    Returns (score, level, recommendation, breakdown).
    """
    if not findings:
        return 0, "low", "no_issues_detected", []

    # Map each rule_id to its highest severity finding
    rule_map: Dict[str, str] = {}
    severity_order = {"high": 1, "medium": 2, "low": 3, "info": 4}

    for f in findings:
        r_id = f["rule_id"]
        sev = f["severity"]
        if r_id not in rule_map or severity_order.get(sev, 5) < severity_order.get(rule_map[r_id], 5):
            rule_map[r_id] = sev

    breakdown = []
    total_points = 0
    for r_id, sev in rule_map.items():
        pts = SEVERITY_POINTS.get(sev, 0)
        total_points += pts
        breakdown.append({
            "rule_id": r_id,
            "severity": sev,
            "points": pts,
        })

    # Sort breakdown by points descending, then rule_id
    breakdown.sort(key=lambda x: (-x["points"], x["rule_id"]))

    score = min(100, total_points)

    if score >= 50:
        level = "high"
        recommendation = "high_priority_review"
    elif score >= 20:
        level = "medium"
        recommendation = "review_recommended"
    else:
        level = "low"
        recommendation = "no_issues_detected"

    return score, level, recommendation, breakdown
