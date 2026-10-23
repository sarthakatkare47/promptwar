import io
from PIL import Image
import pytest


def upload_sample(client, color="cyan") -> str:
    bio = io.BytesIO()
    img = Image.new("RGB", (100, 100), color=color)
    img.save(bio, format="PNG")
    res = client.post(
        "/api/invoices/upload",
        files={"file": (f"{color}.png", bio.getvalue(), "image/png")},
    )
    return res.json()["invoice"]["invoice_id"]


def test_list_and_filters(client):
    inv_id = upload_sample(client, "yellow")

    # List all
    res = client.get("/api/invoices?limit=10")
    assert res.status_code == 200
    data = res.json()
    assert data["total"] >= 1
    assert any(i["invoice_id"] == inv_id for i in data["items"])

    # Search filter
    res_q = client.get("/api/invoices?q=Sharma")
    assert res_q.status_code == 200
    assert len(res_q.json()["items"]) >= 1


def test_patch_revalidates_and_audits(client):
    inv_id = upload_sample(client, "magenta")

    # Get initial invoice
    inv_before = client.get(f"/api/invoices/{inv_id}").json()
    init_run = inv_before["validation_run"]

    # Patch with total mismatch (triggers TAX-002: 10000 + 900 + 900 != 12800)
    patch_res = client.patch(
        f"/api/invoices/{inv_id}",
        json={"fields": {"total_amount": "12800.00"}},
    )
    assert patch_res.status_code == 200
    inv_after = patch_res.json()
    assert inv_after["validation_run"] == init_run + 1
    assert inv_after["fields"]["total_amount"] == "12800.00"

    # Confirm TAX-002 finding generated
    findings_res = client.get(f"/api/invoices/{inv_id}/findings")
    assert findings_res.status_code == 200
    items = findings_res.json()["items"]
    assert any(f["rule_id"] == "TAX-002" for f in items)

    # Check audit trail
    audit_res = client.get(f"/api/invoices/{inv_id}/audit")
    assert audit_res.status_code == 200
    events = audit_res.json()["items"]
    assert any(e["event_type"] == "field_corrected" for e in events)


def test_review_state_machine_and_locking(client):
    inv_id = upload_sample(client, "orange")

    # Flag invoice with comment
    flag_res = client.post(
        f"/api/invoices/{inv_id}/review",
        json={"action": "flag", "comment": "Checking vendor phone number"},
    )
    assert flag_res.status_code == 200
    assert flag_res.json()["invoice"]["review_status"] == "flagged"

    # Approve from flagged
    approve_res = client.post(
        f"/api/invoices/{inv_id}/review",
        json={"action": "approve", "comment": "Phone confirmed"},
    )
    assert approve_res.status_code == 200
    assert approve_res.json()["invoice"]["review_status"] == "approved"

    # Editing locked invoice returns 409 INVOICE_LOCKED
    lock_edit = client.patch(
        f"/api/invoices/{inv_id}",
        json={"fields": {"vendor_name": "New Name"}},
    )
    assert lock_edit.status_code == 409
    assert lock_edit.json()["error"]["code"] == "INVOICE_LOCKED"

    # Reopen invoice
    reopen_res = client.post(
        f"/api/invoices/{inv_id}/review",
        json={"action": "reopen", "comment": "Need to amend line items"},
    )
    assert reopen_res.status_code == 200
    assert reopen_res.json()["invoice"]["review_status"] == "pending"

    # Now edit succeeds
    unlocked_edit = client.patch(
        f"/api/invoices/{inv_id}",
        json={"fields": {"vendor_name": "Sharma Traders Updated"}},
    )
    assert unlocked_edit.status_code == 200
