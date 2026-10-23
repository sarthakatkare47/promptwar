import ast
from pathlib import Path


def test_validation_layer_has_no_impure_imports():
    """NFR-009: app/validation must not import from extraction, db, api, or services."""
    validation_dir = Path(__file__).resolve().parent.parent.parent / "app" / "validation"
    forbidden_prefixes = ("app.extraction", "app.db", "app.api", "app.services")

    for py_file in validation_dir.glob("*.py"):
        with open(py_file, "r", encoding="utf-8") as f:
            tree = ast.parse(f.read(), filename=str(py_file))

        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                for alias in node.names:
                    for forbidden in forbidden_prefixes:
                        assert not alias.name.startswith(forbidden), f"{py_file.name} imports {alias.name}"
            elif isinstance(node, ast.ImportFrom):
                if node.module:
                    for forbidden in forbidden_prefixes:
                        assert not node.module.startswith(forbidden), f"{py_file.name} imports from {node.module}"
