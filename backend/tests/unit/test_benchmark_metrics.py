import pytest
from benchmark.metrics import (
    compute_detection_rate,
    compute_duplicate_metrics,
    compute_false_positive_rate,
    compute_field_accuracy,
    compute_injection_pass_rate,
    compute_latency_percentiles,
)


def test_compute_field_accuracy():
    labels = [{"fields": {"vendor_name": "Sharma", "total_amount": "100.00"}}]
    preds = [{"fields": {"vendor_name": "Sharma", "total_amount": "100.00"}}]
    res = compute_field_accuracy(labels, preds)
    assert res["value"] == 1.0
    assert res["correct"] == 2
    assert res["total"] == 2


def test_compute_detection_rate():
    planted = [
        {"expected_rule_id": "GST-001", "findings": [{"rule_id": "GST-001"}]},
        {"expected_rule_id": "TAX-002", "findings": [{"rule_id": "TAX-002"}]},
    ]
    res = compute_detection_rate(planted)
    assert res["value"] == 1.0
    assert res["detected"] == 2


def test_compute_false_positive_rate():
    clean = [
        {"id": "c1", "risk_level": "low", "findings": []},
        {"id": "c2", "risk_level": "low", "findings": []},
    ]
    res = compute_false_positive_rate(clean)
    assert res["value"] == 0.0
    assert res["flagged_clean"] == 0


def test_compute_duplicate_metrics():
    evals = [
        {"is_duplicate": True, "duplicate_rule_fired": True},    # TP
        {"is_duplicate": False, "duplicate_rule_fired": False},  # TN
    ]
    res = compute_duplicate_metrics(evals)
    assert res["precision"] == 1.0
    assert res["recall"] == 1.0
    assert res["tp"] == 1


def test_compute_latency_percentiles():
    durations = [10.0, 20.0, 30.0, 40.0, 50.0]
    res = compute_latency_percentiles(durations)
    assert res["n"] == 5
    assert res["p50"] == 30.0
    assert res["p95"] == 50.0
