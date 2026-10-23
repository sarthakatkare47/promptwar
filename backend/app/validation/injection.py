import re
import secrets
from typing import Any, Dict, List

# Targeted injection patterns that signal untrusted instructions
INJECTION_PATTERNS = [
    re.compile(r"\bignore\s+(?:previous|all|prior|above)\s+instructions\b", re.IGNORECASE),
    re.compile(r"\bmark\s+(?:this\s+)?(?:invoice\s+)?as\s+(?:approved|paid|verified)\b", re.IGNORECASE),
    re.compile(r"\bset\s+total\s+(?:amount\s+)?to\s+0\b", re.IGNORECASE),
    re.compile(r"\bprint\s+(?:the\s+)?(?:api[_\s]?key|system\s+prompt|credentials)\b", re.IGNORECASE),
    re.compile(r"\breveal\s+(?:the\s+)?(?:secret|api[_\s]?key|prompt)\b", re.IGNORECASE),
    re.compile(r"\b(?:system\s+prompt|system\s+instruction)\s*[:=]", re.IGNORECASE),
    re.compile(r"\bdisregard\s+(?:safety|all|previous)\s+rules\b", re.IGNORECASE),
    re.compile(r"\boutput\s+only\s+(?:json|the\s+following)\b", re.IGNORECASE),
]


def check_injection_heuristic(fields: Dict[str, Any], line_items: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    findings = []
    
    # Strings to scan
    strings_to_check = []
    for k, v in fields.items():
        if isinstance(v, str) and v.strip():
            strings_to_check.append((f"fields.{k}", v))

    for idx, item in enumerate(line_items, start=1):
        desc = item.get("description")
        if isinstance(desc, str) and desc.strip():
            strings_to_check.append((f"line_items[{idx}].description", desc))

    for field_name, text in strings_to_check:
        for pat in INJECTION_PATTERNS:
            match = pat.search(text)
            if match:
                findings.append({
                    "finding_id": f"fnd_{secrets.token_hex(6)}",
                    "rule_id": "INJ-001",
                    "severity": "medium",
                    "category": "safety",
                    "title": "Instruction-like text detected in document",
                    "explanation": "Text inside the invoice matches patterns often used in prompt-injection attempts. The system does not execute instructions found in invoices; this finding is a review signal for the human evaluator.",
                    "evidence": {
                        "field": field_name,
                        "matched_pattern": match.group(0),
                    },
                })
                return findings  # Flag once per invoice

    return findings
