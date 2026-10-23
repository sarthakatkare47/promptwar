import pytest


def test_export_invoices_and_findings_csv(client):
    # Export invoices
    res_inv = client.get("/api/reports/export?scope=invoices")
    assert res_inv.status_code == 200
    assert "text/csv" in res_inv.headers["Content-Type"]
    content_inv = res_inv.text
    assert "invoice_id" in content_inv
    assert "total_amount" in content_inv

    # Export findings
    res_fnd = client.get("/api/reports/export?scope=findings")
    assert res_fnd.status_code == 200
    assert "text/csv" in res_fnd.headers["Content-Type"]
    content_fnd = res_fnd.text
    assert "rule_id" in content_fnd
    assert "severity" in content_fnd
