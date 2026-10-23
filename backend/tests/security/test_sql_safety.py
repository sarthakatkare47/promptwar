import pytest
from app.db.connection import get_connection
from app.db.repository import InvoiceRepository


def test_sql_injection_in_search_query():
    hostile_queries = [
        "' OR '1'='1",
        "'; DROP TABLE invoices; --",
        "UNION SELECT * FROM sqlite_master --",
        "' OR 1=1; --",
        "\\'; EXEC xp_cmdshell('dir'); --",
    ]

    with get_connection() as conn:
        for hostile_q in hostile_queries:
            # Should safely execute parameterized query without SQL syntax error or unintended data leakage
            items, total = InvoiceRepository.list_invoices(conn=conn, q=hostile_q)
            assert isinstance(items, list)
            assert isinstance(total, int)

        # Confirm invoices table still intact
        cursor = conn.cursor()
        cursor.execute("SELECT COUNT(*) FROM invoices")
        assert cursor.fetchone() is not None
