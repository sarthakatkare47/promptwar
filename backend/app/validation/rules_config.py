from decimal import Decimal
from typing import Dict, Set

# Indian State & Union Territory Codes (01-38, 97, 99)
VALID_STATE_CODES: Set[str] = {
    f"{i:02d}" for i in range(1, 39)
} | {"97", "99"}

# Severities and point values
SEVERITY_POINTS: Dict[str, int] = {
    "high": 50,
    "medium": 25,
    "low": 10,
    "info": 0,
}

# Default tolerances
DEFAULT_AMOUNT_TOLERANCE_INR: Decimal = Decimal("1.00")
DEFAULT_CGST_SGST_TOLERANCE_INR: Decimal = Decimal("0.05")
DEFAULT_OLD_INVOICE_DAYS: int = 730
