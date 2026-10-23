from decimal import Decimal
import pytest
from app.validation.money import (
    clean_and_parse_money,
    format_money,
    money_to_paise,
    paise_to_money,
    quantize_money,
)


def test_clean_and_parse_money_valid():
    assert clean_and_parse_money("10000.00") == Decimal("10000.00")
    assert clean_and_parse_money("10,000.00") == Decimal("10000.00")
    assert clean_and_parse_money("₹ 1,18,000.50") == Decimal("118000.50")
    assert clean_and_parse_money("Rs. 900") == Decimal("900.00")
    assert clean_and_parse_money("0") == Decimal("0.00")
    assert clean_and_parse_money("0.05") == Decimal("0.05")


def test_clean_and_parse_money_invalid():
    assert clean_and_parse_money(None) is None
    assert clean_and_parse_money("") is None
    assert clean_and_parse_money("   ") is None
    assert clean_and_parse_money("-500.00") is None  # Negative rejected
    assert clean_and_parse_money("1e5") is None  # Scientific notation rejected
    assert clean_and_parse_money("abc") is None
    assert clean_and_parse_money("10.999") is None  # More than 2 decimal places rejected by regex


def test_money_paise_conversions():
    d = Decimal("123.45")
    paise = money_to_paise(d)
    assert paise == 12345
    assert paise_to_money(paise) == d
    assert format_money(d) == "123.45"
    assert money_to_paise(None) is None
    assert paise_to_money(None) is None


def test_float_trap_safety():
    # 0.1 + 0.2 in floating point is 0.30000000000000004
    # With Decimal, clean arithmetic is preserved
    d1 = clean_and_parse_money("0.10")
    d2 = clean_and_parse_money("0.20")
    assert (d1 + d2) == Decimal("0.30")
