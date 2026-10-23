import secrets
from typing import Any, Dict, List, Optional


def check_extraction_rules(
    fields: Dict[str, Any],
    uncertain_fields: List[Dict[str, str]],
    document_type: Optional[str] = None,
) -> List[Dict[str, Any]]:
    findings = []

    # EXT-001: Missing required fields
    required = ["vendor_name", "invoice_number", "invoice_date", "total_amount"]
    missing = [f for f in required if not fields.get(f)]
    if missing:
        findings.append({
            "finding_id": f"fnd_{secrets.token_hex(6)}",
            "rule_id": "EXT-001",
            "severity": "medium",
            "category": "extraction",
            "title": "Required invoice fields are missing",
            "explanation": "One or more core invoice fields (vendor name, invoice number, invoice date, or total amount) could not be extracted from the document.",
            "evidence": {"missing_fields": missing},
        })

    # EXT-002: Field uncertainty signal
    if uncertain_fields:
        findings.append({
            "finding_id": f"fnd_{secrets.token_hex(6)}",
            "rule_id": "EXT-002",
            "severity": "low",
            "category": "extraction",
            "title": "One or more fields flagged as uncertain",
            "explanation": "The extraction model or normalizer flagged fields as unclear, ambiguous, or lacking direct text evidence. Please review these fields before approval.",
            "evidence": {"uncertain_fields": uncertain_fields},
        })

    # EXT-003: Document classification
    if document_type in ("other", "not_an_invoice"):
        findings.append({
            "finding_id": f"fnd_{secrets.token_hex(6)}",
            "rule_id": "EXT-003",
            "severity": "medium",
            "category": "extraction",
            "title": "Uploaded document may not be a tax invoice",
            "explanation": f"The model classified this document as '{document_type}', rather than a standard tax invoice or bill of supply.",
            "evidence": {"document_type": document_type},
        })

    return findings
