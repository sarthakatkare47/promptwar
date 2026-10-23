import re
from decimal import Decimal, InvalidOperation, ROUND_HALF_UP
from typing import Any, Optional

MONEY_REGEX = re.compile(r"^\d{1,12}(\.\d{1,2})?$")
TWO_PLACES = Decimal("0.01")


def clean_and_parse_money(val: Any) -> Optional[Decimal]:
    r"""
    Cleans raw amount strings (stripping currency symbols, spaces, Indian/western commas).
    Validates strictly against ^\d{1,12}(\.\d{1,2})?$ and returns quantised Decimal.
    Negative values or unparseable formats return None.
    """
    if val is None:
        return None
    
    s = str(val).strip()
    if not s:
        return None

    # Strip currency indicators and formatting characters
    s = s.replace("₹", "").replace("Rs.", "").replace("Rs", "").replace(",", "").replace(" ", "")
    
    if not MONEY_REGEX.match(s):
        return None
        
    try:
        d = Decimal(s)
        if d < 0:
            return None
        return quantize_money(d)
    except (InvalidOperation, ValueError):
        return None


def quantize_money(d: Decimal) -> Decimal:
    """Quantises Decimal to 2 decimal places with ROUND_HALF_UP."""
    return d.quantize(TWO_PLACES, rounding=ROUND_HALF_UP)


def money_to_paise(d: Optional[Decimal]) -> Optional[int]:
    if d is None:
        return None
    return int(quantize_money(d) * 100)


def paise_to_money(p: Optional[int]) -> Optional[Decimal]:
    if p is None:
        return None
    return quantize_money(Decimal(p) / Decimal(100))


def str_to_paise(val: Any) -> Optional[int]:
    d = clean_and_parse_money(val)
    if d is None:
        return None
    return money_to_paise(d)


def paise_to_str(p: Optional[int]) -> Optional[str]:
    d = paise_to_money(p)
    return format_money(d)


def format_money(d: Optional[Decimal]) -> Optional[str]:
    if d is None:
        return None
    return f"{quantize_money(d):.2f}"

