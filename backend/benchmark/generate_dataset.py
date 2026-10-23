import argparse
import hashlib
import json
import random
from pathlib import Path
from PIL import Image, ImageDraw, ImageFont
from benchmark.attacks import ATTACK_FIXTURES, BENIGN_LOOKALIKES
from app.validation.gstin import compute_gstin_checksum


def render_invoice_image(output_path: Path, invoice_data: dict):
    img = Image.new("RGB", (800, 1000), color=(255, 255, 255))
    draw = ImageDraw.Draw(img)
    font = ImageFont.load_default()

    draw.rectangle([(20, 20), (780, 980)], outline=(180, 180, 180), width=2)
    draw.text((40, 40), f"TAX INVOICE - {invoice_data.get('vendor_name', 'VENDOR')}", fill=(20, 20, 20), font=font)
    draw.text((40, 70), f"GSTIN: {invoice_data.get('vendor_gstin', 'N/A')}", fill=(60, 60, 60), font=font)
    draw.text((40, 90), f"Invoice No: {invoice_data.get('invoice_number', 'N/A')}", fill=(60, 60, 60), font=font)
    draw.text((40, 110), f"Date: {invoice_data.get('invoice_date', 'N/A')}", fill=(60, 60, 60), font=font)

    draw.line([(40, 140), (760, 140)], fill=(200, 200, 200), width=1)
    draw.text((40, 160), "Line Items:", fill=(40, 40, 40), font=font)

    y = 190
    for idx, item in enumerate(invoice_data.get("line_items", [])):
        draw.text((50, y), f"{idx+1}. {item.get('description', '')} - Qty: {item.get('quantity', '')} - Amt: {item.get('amount', '')}", fill=(50, 50, 50), font=font)
        y += 25

    draw.line([(40, y + 10), (760, y + 10)], fill=(200, 200, 200), width=1)
    y += 30
    draw.text((450, y), f"Taxable Amount: INR {invoice_data.get('taxable_amount', '0.00')}", fill=(40, 40, 40), font=font)
    y += 20
    draw.text((450, y), f"CGST: INR {invoice_data.get('cgst', '0.00')}", fill=(40, 40, 40), font=font)
    y += 20
    draw.text((450, y), f"SGST: INR {invoice_data.get('sgst', '0.00')}", fill=(40, 40, 40), font=font)
    if invoice_data.get("igst"):
        y += 20
        draw.text((450, y), f"IGST: INR {invoice_data.get('igst', '0.00')}", fill=(40, 40, 40), font=font)
    y += 25
    draw.text((450, y), f"Total Amount: INR {invoice_data.get('total_amount', '0.00')}", fill=(0, 0, 0), font=font)

    output_path.parent.mkdir(parents=True, exist_ok=True)
    img.save(output_path, format="PNG")


def generate_dataset(seed: int = 42, target_dir: Path = None):
    random.seed(seed)
    base_dir = target_dir or Path(__file__).resolve().parent / "dataset"
    labels_dir = base_dir / "labels"
    images_dir = base_dir / "images"
    labels_dir.mkdir(parents=True, exist_ok=True)
    images_dir.mkdir(parents=True, exist_ok=True)

    cases = []

    # 1. Clean Invoices
    clean_invoices = [
        {
            "id": "clean_01",
            "type": "clean",
            "fields": {
                "vendor_name": "Sharma Traders",
                "vendor_gstin": "27ABCDE1234F1Z0",
                "buyer_gstin": "27XYZAB5678C1Z6",
                "invoice_number": "ST/24-25/0142",
                "invoice_date": "2025-03-14",
                "currency": "INR",
                "taxable_amount": "10000.00",
                "cgst": "900.00",
                "sgst": "900.00",
                "igst": None,
                "total_amount": "11800.00",
            },
            "line_items": [{"description": "Steel bolts M8", "quantity": "100", "unit_price": "100.00", "amount": "10000.00"}],
        },
        {
            "id": "clean_02",
            "type": "clean",
            "fields": {
                "vendor_name": "Bharat Electronics",
                "vendor_gstin": "29AABCB1234A1ZE",
                "buyer_gstin": "29XYZAB5678B1Z4",
                "invoice_number": "BE-2025-889",
                "invoice_date": "2025-02-10",
                "currency": "INR",
                "taxable_amount": "50000.00",
                "cgst": "4500.00",
                "sgst": "4500.00",
                "igst": None,
                "total_amount": "59000.00",
            },
            "line_items": [{"description": "Circuit boards", "quantity": "50", "unit_price": "1000.00", "amount": "50000.00"}],
        },
    ]

    for c in clean_invoices:
        cases.append(c)

    # 2. Planted Error Invoices
    planted_cases = [
        {
            "id": "planted_bad_gstin_format",
            "type": "planted_error",
            "expected_rule_id": "GST-001",
            "fields": {
                "vendor_name": "Faulty Vendor",
                "vendor_gstin": "INVALID_GSTIN_123",
                "invoice_number": "FV-01",
                "invoice_date": "2025-03-14",
                "taxable_amount": "1000.00",
                "cgst": "90.00",
                "sgst": "90.00",
                "total_amount": "1180.00",
            },
            "line_items": [{"description": "Item A", "amount": "1000.00"}],
        },
        {
            "id": "planted_bad_gstin_checksum",
            "type": "planted_error",
            "expected_rule_id": "GST-002",
            "fields": {
                "vendor_name": "Checksum Mismatch Vendor",
                "vendor_gstin": "27ABCDE1234F1Z9",  # check char should be 0
                "invoice_number": "FV-02",
                "invoice_date": "2025-03-14",
                "taxable_amount": "1000.00",
                "cgst": "90.00",
                "sgst": "90.00",
                "total_amount": "1180.00",
            },
            "line_items": [{"description": "Item A", "amount": "1000.00"}],
        },
        {
            "id": "planted_total_mismatch",
            "type": "planted_error",
            "expected_rule_id": "TAX-002",
            "fields": {
                "vendor_name": "Total Mismatch Supplier",
                "vendor_gstin": "27ABCDE1234F1Z0",
                "invoice_number": "FV-03",
                "invoice_date": "2025-03-14",
                "taxable_amount": "10000.00",
                "cgst": "900.00",
                "sgst": "900.00",
                "total_amount": "14500.00",  # Expected 11800.00
            },
            "line_items": [{"description": "Item A", "amount": "10000.00"}],
        },
        {
            "id": "planted_cgst_sgst_mismatch",
            "type": "planted_error",
            "expected_rule_id": "TAX-003",
            "fields": {
                "vendor_name": "Tax Split Supplier",
                "vendor_gstin": "27ABCDE1234F1Z0",
                "invoice_number": "FV-04",
                "invoice_date": "2025-03-14",
                "taxable_amount": "10000.00",
                "cgst": "900.00",
                "sgst": "1000.00",  # CGST != SGST
                "total_amount": "11900.00",
            },
            "line_items": [{"description": "Item A", "amount": "10000.00"}],
        },
        {
            "id": "planted_future_date",
            "type": "planted_error",
            "expected_rule_id": "DATE-002",
            "fields": {
                "vendor_name": "Future Date Supplier",
                "vendor_gstin": "27ABCDE1234F1Z0",
                "invoice_number": "FV-05",
                "invoice_date": "2035-01-01",
                "taxable_amount": "2000.00",
                "cgst": "180.00",
                "sgst": "180.00",
                "total_amount": "2360.00",
            },
            "line_items": [{"description": "Item A", "amount": "2000.00"}],
        },
    ]

    for p in planted_cases:
        cases.append(p)

    # 3. Duplicate Pairs
    dup_cases = [
        {
            "id": "dup_primary",
            "type": "duplicate_target",
            "fields": {
                "vendor_name": "Unique Vendor A",
                "vendor_gstin": "27ABCDE1234F1Z0",
                "invoice_number": "DUP-101",
                "invoice_date": "2025-03-14",
                "total_amount": "5000.00",
            },
        },
        {
            "id": "dup_exact",
            "type": "duplicate_eval",
            "is_duplicate": True,
            "expected_rule_id": "DUP-001",
            "fields": {
                "vendor_name": "Unique Vendor A",
                "vendor_gstin": "27ABCDE1234F1Z0",
                "invoice_number": "DUP-101",
                "invoice_date": "2025-03-14",
                "total_amount": "5000.00",
            },
        },
    ]
    for d in dup_cases:
        cases.append(d)

    # 4. Attack Cases and Benign Lookalikes
    for att in ATTACK_FIXTURES:
        cases.append({
            "id": att["id"],
            "type": "attack",
            "text": att["text"],
            "fields": {
                "vendor_name": att["text"],
                "vendor_gstin": "27ABCDE1234F1Z0",
                "invoice_number": f"ATT-{att['id']}",
                "invoice_date": "2025-03-14",
                "total_amount": "1000.00",
            },
        })

    for ben in BENIGN_LOOKALIKES:
        cases.append({
            "id": ben["id"],
            "type": "benign",
            "text": ben["text"],
            "fields": {
                "vendor_name": ben["text"],
                "vendor_gstin": "27ABCDE1234F1Z0",
                "invoice_number": f"BEN-{ben['id']}",
                "invoice_date": "2025-03-14",
                "total_amount": "1000.00",
            },
        })

    # Render images and save labels
    manifest_entries = []
    for c in cases:
        c_id = c["id"]
        label_file = labels_dir / f"{c_id}.json"
        image_file = images_dir / f"{c_id}.png"

        render_invoice_image(image_file, c.get("fields", {}))

        with open(image_file, "rb") as f:
            img_sha256 = hashlib.sha256(f.read()).hexdigest()

        c["image_sha256"] = img_sha256
        with open(label_file, "w", encoding="utf-8") as f:
            json.dump(c, f, indent=2)

        manifest_entries.append({
            "id": c_id,
            "type": c.get("type"),
            "image_path": f"images/{c_id}.png",
            "label_path": f"labels/{c_id}.json",
            "image_sha256": img_sha256,
        })

    manifest = {
        "seed": seed,
        "case_count": len(manifest_entries),
        "clean_cases": len(clean_invoices),
        "planted_error_cases": len(planted_cases),
        "duplicate_pairs": 1,
        "attack_cases": len(ATTACK_FIXTURES),
        "benign_cases": len(BENIGN_LOOKALIKES),
        "entries": manifest_entries,
    }

    manifest_file = base_dir / "manifest.json"
    with open(manifest_file, "w", encoding="utf-8") as f:
        json.dump(manifest, f, indent=2)

    print(f"Dataset generated successfully at {base_dir} (Cases: {len(manifest_entries)})")
    return manifest


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--seed", type=int, default=42)
    args = parser.parse_args()
    generate_dataset(seed=args.seed)
