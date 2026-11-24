import os
import sys
import tempfile
from pathlib import Path

_tmp = tempfile.mkdtemp()
os.environ["GA_DATABASE_URL"] = f"sqlite:///{_tmp}/test.db"
os.environ["GA_FRONTEND_DIST"] = f"{_tmp}/yok"
os.environ["GA_DATA_DIR"] = f"{_tmp}/data"
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import pytest  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402

from app.main import app  # noqa: E402

LEAD = {"X-User-Id": "burak"}
AYSE = {"X-User-Id": "ayse"}


@pytest.fixture(scope="session")
def client():
    with TestClient(app) as c:
        yield c
