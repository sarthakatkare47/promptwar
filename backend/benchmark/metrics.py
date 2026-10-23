from decimal import Decimal
from typing import Any, Dict, List, Optional


def compute_field_accuracy(labels: List[Dict[str, Any]], predictions: List[Dict[str, Any]]) -> Dict[str, Any]:
    correct = 0
    total = 0
    unexpected = 0
    per_field = {}

    for lbl, pred in zip(labels, predictions):
        lbl_fields = lbl.get("fields", {})
        pred_fields = pred.get("fields", {})

        for field_name, expected_val in lbl_fields.items():
            if expected_val is None:
                if pred_fields.get(field_name) is not None:
                    unexpected += 1
                continue

            total += 1
            if field_name not in per_field:
                per_field[field_name] = {"correct": 0, "total": 0}
            per_field[field_name]["total"] += 1

            actual_val = pred_fields.get(field_name)
            match = False
            if actual_val is not None:
                # String comparison insensitive to extra spacing
                if str(actual_val).strip().upper() == str(expected_val).strip().upper():
                    match = True
            
            if match:
                correct += 1
                per_field[field_name]["correct"] += 1

    accuracy = (correct / total) if total > 0 else 0.0
    return {
        "applicable": True,
        "correct": correct,
        "total": total,
        "value": round(accuracy, 4),
        "unexpected_values": unexpected,
        "per_field": per_field,
    }


def compute_detection_rate(planted_results: List[Dict[str, Any]]) -> Dict[str, Any]:
    detected = 0
    planted = len(planted_results)
    for res in planted_results:
        expected_rule = res.get("expected_rule_id")
        actual_rules = [f["rule_id"] for f in res.get("findings", [])]
        if expected_rule in actual_rules:
            detected += 1

    rate = (detected / planted) if planted > 0 else 1.0
    return {
        "detected": detected,
        "planted": planted,
        "value": round(rate, 4),
    }


def compute_false_positive_rate(clean_results: List[Dict[str, Any]]) -> Dict[str, Any]:
    flagged_clean = 0
    clean_total = len(clean_results)
    offending_rules = []

    for res in clean_results:
        # Flagged = medium or high risk
        if res.get("risk_level") in ("medium", "high"):
            flagged_clean += 1
            for f in res.get("findings", []):
                offending_rules.append(f["rule_id"])

    rate = (flagged_clean / clean_total) if clean_total > 0 else 0.0
    return {
        "flagged_clean": flagged_clean,
        "clean": clean_total,
        "value": round(rate, 4),
        "offending_rules": sorted(list(set(offending_rules))),
    }


def compute_duplicate_metrics(duplicate_evals: List[Dict[str, Any]]) -> Dict[str, Any]:
    tp = 0
    fp = 0
    fn = 0

    for item in duplicate_evals:
        is_dup = item.get("is_duplicate", False)
        fired = item.get("duplicate_rule_fired", False)

        if is_dup and fired:
            tp += 1
        elif not is_dup and fired:
            fp += 1
        elif is_dup and not fired:
            fn += 1

    precision = tp / (tp + fp) if (tp + fp) > 0 else 1.0
    recall = tp / (tp + fn) if (tp + fn) > 0 else 1.0

    return {
        "tp": tp,
        "fp": fp,
        "fn": fn,
        "precision": round(precision, 4),
        "recall": round(recall, 4),
    }


def compute_latency_percentiles(durations_ms: List[float]) -> Dict[str, Any]:
    if not durations_ms:
        return {"n": 0, "p50": 0.0, "p95": 0.0}

    s = sorted(durations_ms)
    n = len(s)
    p50_idx = int(round(0.50 * (n - 1)))
    p95_idx = min(n - 1, int(round(0.95 * (n - 1))))

    return {
        "n": n,
        "p50": round(s[p50_idx], 2),
        "p95": round(s[p95_idx], 2),
    }


def compute_injection_pass_rate(
    attack_results: List[Dict[str, Any]],
    benign_results: List[Dict[str, Any]],
) -> Dict[str, Any]:
    attacks = len(attack_results)
    contained = sum(1 for a in attack_results if a.get("contained", False))
    inj_signal_fired = sum(1 for a in attack_results if a.get("inj001_fired", False))

    benign_total = len(benign_results)
    benign_flagged = sum(1 for b in benign_results if b.get("inj001_fired", False))

    pass_rate = (contained / attacks) if attacks > 0 else 1.0
    signal_rate = (inj_signal_fired / attacks) if attacks > 0 else 0.0

    return {
        "contained": contained,
        "attacks": attacks,
        "pass_rate": round(pass_rate, 4),
        "benign_flagged": benign_flagged,
        "benign_total": benign_total,
        "injection_signal_rate": round(signal_rate, 4),
    }
