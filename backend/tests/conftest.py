import os
import shutil
import tempfile
from pathlib import Path
import pytest
from fastapi.testclient import TestClient

from app.config import settings
from app.db.connection import init_db
from app.main import app


@pytest.fixture(scope="session", autouse=True)
def setup_test_environment():
    temp_dir = tempfile.mkdtemp(prefix="invoiceguard_test_")
    db_file = Path(temp_dir) / "test.db"
    uploads_dir = Path(temp_dir) / "uploads"
    uploads_dir.mkdir(parents=True, exist_ok=True)

    # Override settings
    settings.DATABASE_PATH = str(db_file)
    settings.UPLOAD_DIR = str(uploads_dir)
    settings.EXTRACTOR = "mock"

    init_db(db_file)

    yield

    shutil.rmtree(temp_dir, ignore_errors=True)


@pytest.fixture
def client():
    with TestClient(app) as test_client:
        yield test_client
