import urllib.request
import json
import mimetypes
import uuid
import sys

BASE = "http://localhost:5173"

def post_multipart(url, file_path, field_name="file"):
    boundary = uuid.uuid4().hex
    with open(file_path, "rb") as f:
        file_bytes = f.read()
    
    filename = file_path.replace("\\", "/").split("/")[-1]
    mime_type = mimetypes.guess_type(filename)[0] or "application/octet-stream"

    body = (
        f"--{boundary}\r\n"
        f'Content-Disposition: form-data; name="{field_name}"; filename="{filename}"\r\n'
        f"Content-Type: {mime_type}\r\n\r\n"
    ).encode("utf-8") + file_bytes + f"\r\n--{boundary}--\r\n".encode("utf-8")

    req = urllib.request.Request(url, data=body)
    req.add_header("Content-Type", f"multipart/form-data; boundary={boundary}")
    with urllib.request.urlopen(req) as resp:
        return json.loads(resp.read().decode("utf-8"))

def send_json(url, data, method="POST"):
    body = json.dumps(data).encode("utf-8")
    req = urllib.request.Request(url, data=body, method=method)
    req.add_header("Content-Type", "application/json")
    with urllib.request.urlopen(req) as resp:
        return json.loads(resp.read().decode("utf-8"))

def main():
    print(f"Starting E2E Verification against Vite Frontend at {BASE}...")

    # 1. Health check via Vite proxy
    res = json.loads(urllib.request.urlopen(f"{BASE}/health").read())
    print(f"[1] Health Check: status='{res['status']}', version='{res['version']}'")
    assert res["status"] == "ok"

    # 2. Scorecard check via Vite proxy
    res_sc = json.loads(urllib.request.urlopen(f"{BASE}/api/scorecard").read())
    print(f"[2] Scorecard Check: status='{res_sc['status']}', mode='{res_sc.get('mode')}'")
    assert res_sc["status"] == "ok"

    # 3. Upload clean invoice via Vite proxy
    clean_file = r"backend/benchmark/dataset/images/clean_01.png"
    raw_upload = post_multipart(f"{BASE}/api/invoices/upload", clean_file)
    upload_res = raw_upload.get("invoice", raw_upload)
    inv_id = upload_res["invoice_id"]
    filename = upload_res["original_filename"]
    print(f"[3] Uploaded Invoice: id={inv_id}, file='{filename}'")
    assert filename == "clean_01.png"

    # If already approved from prior run, reopen it first
    if upload_res.get("review_status") in ("approved", "rejected"):
        print("    Invoice was locked from prior run; testing reopen action...")
        reopen_res = send_json(f"{BASE}/api/invoices/{inv_id}/review", {"action": "reopen", "comment": "Reopening for test suite"})
        print("    Reopened status:", reopen_res.get("invoice", {}).get("review_status"))

    # 4. Patch fields (field correction) via Vite proxy
    patch_res = send_json(f"{BASE}/api/invoices/{inv_id}", {"fields": {"vendor_name": "Acme Super Clean Vendor Ltd"}}, method="PATCH")
    print(f"[4] Field Correction: vendor_name='{patch_res['fields']['vendor_name']}'")
    assert patch_res["fields"]["vendor_name"] == "Acme Super Clean Vendor Ltd"

    # 5. Review decision (Approve) via Vite proxy
    raw_rev = send_json(f"{BASE}/api/invoices/{inv_id}/review", {
        "action": "approve",
        "comment": "Cleared invoice after vendor entity verification",
        "acknowledge_risk": True
    })
    rev_res = raw_rev.get("invoice", raw_rev)
    print(f"[5] Review Decision Status: '{rev_res['review_status']}'")
    assert rev_res["review_status"] == "approved"

    # 6. Audit trail check via Vite proxy
    req_audit = urllib.request.urlopen(f"{BASE}/api/invoices/{inv_id}/audit")
    audit_data = json.loads(req_audit.read().decode("utf-8"))
    audit_res = audit_data.get("items", audit_data)
    event_types = [a["event_type"] for a in audit_res]
    print(f"[6] Audit Trail Events: {event_types}")
    assert any("review" in e for e in event_types)

    # 7. List invoices via Vite proxy
    list_res = json.loads(urllib.request.urlopen(f"{BASE}/api/invoices").read())
    print(f"[7] Total Invoices in Register: {list_res['total']}")
    assert list_res["total"] >= 1

    # 8. CSV export via Vite proxy
    csv_bytes = urllib.request.urlopen(f"{BASE}/api/reports/export?scope=invoices").read()
    csv_text = csv_bytes.decode("utf-8")
    lines = csv_text.strip().splitlines()
    print(f"[8] CSV Export: {len(lines)} lines returned")
    assert len(lines) >= 2

    # 9. Upload an adversarial mismatch invoice to verify high risk detection
    mismatch_file = r"backend/benchmark/dataset/images/planted_total_mismatch.png"
    raw_mismatch = post_multipart(f"{BASE}/api/invoices/upload", mismatch_file)
    mismatch_res = raw_mismatch.get("invoice", raw_mismatch)
    print(f"[9] Mismatch Invoice: id={mismatch_res['invoice_id']}, risk_score={mismatch_res['risk']['score']}, risk_level={mismatch_res['risk']['level']}")
    assert mismatch_res["risk"]["level"] == "high"

    # 10. Fetch findings for mismatch invoice
    req_findings = urllib.request.urlopen(f"{BASE}/api/invoices/{mismatch_res['invoice_id']}/findings")
    findings_data = json.loads(req_findings.read().decode("utf-8"))
    findings = findings_data.get("items", findings_data)
    print(f"[10] Detailed Findings for Mismatch: {len(findings)} findings")
    assert any(f["rule_id"] == "RULE-TAX-001" for f in findings)

    print("\n=======================================================")
    print(">>> ALL 10 E2E FRONTEND-BACKEND INTEGRATION TESTS PASSED! <<<")
    print("=======================================================\n")

if __name__ == "__main__":
    main()
