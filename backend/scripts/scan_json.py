import json
import sys
from pathlib import Path
from app.validation.engine import scan_invoice


def main():
    if len(sys.argv) < 2:
        print("Usage: python -m scripts.scan_json <path_to_invoice.json>")
        sys.exit(1)

    json_path = Path(sys.argv[1])
    if not json_path.exists():
        print(f"Error: file not found: {json_path}")
        sys.exit(1)

    with open(json_path, "r", encoding="utf-8") as f:
        data = json.load(f)

    # Support either direct fields dict or ExtractionResult schema
    fields = data.get("fields", data)
    line_items = data.get("line_items", [])
    uncertain = data.get("uncertain_fields", [])
    doc_type = data.get("document_type", "tax_invoice")

    res = scan_invoice(
        invoice_id="inv_cli_preview",
        fields=fields,
        line_items=line_items,
        history=[],
        uncertain_fields=uncertain,
        document_type=doc_type,
    )

    print("=" * 60)
    print(f"InvoiceGuard+ Scan Results: {json_path.name}")
    print("=" * 60)
    print(f"Risk Level    : {res.risk_level.upper()}")
    print(f"Risk Score    : {res.risk_score} / 100")
    print(f"Recommendation: {res.recommendation}")
    print(f"Findings ({len(res.findings)}):")
    for idx, f in enumerate(res.findings, 1):
        print(f"  {idx}. [{f['severity'].upper()}] {f['rule_id']}: {f['title']}")
        print(f"     Explanation: {f['explanation']}")
        print(f"     Evidence   : {f['evidence']}")
    print("=" * 60)


if __name__ == "__main__":
    main()
