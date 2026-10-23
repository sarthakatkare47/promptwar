import pytest
from app.services.export import sanitize_csv_cell


def test_csv_injection_neutralisation():
    dangerous_inputs = [
        "=HYPERLINK('http://attacker.com','Click Me')",
        "+cmd|' /C calc'!A0",
        "-2+3+cmd|' /C calc'!A0",
        "@SUM(A1:A10)",
        "\tmalicious_tab",
        "\rmalicious_cr",
    ]

    for item in dangerous_inputs:
        sanitized = sanitize_csv_cell(item)
        assert sanitized.startswith("'"), f"Failed to neutralise dangerous cell: {item}"
        assert sanitized[1:] == item


def test_csv_injection_normal_cells_untouched():
    benign_inputs = [
        "Sharma Traders",
        "10000.00",
        "ST/24-25/0142",
        "27ABCDE1234F1Z0",
        "Steel bolts M8",
        None,
    ]

    for item in benign_inputs:
        sanitized = sanitize_csv_cell(item)
        if item is None:
            assert sanitized == ""
        else:
            assert sanitized == item
            assert not sanitized.startswith("'")
