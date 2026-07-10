import os

import pytest
from fastapi.testclient import TestClient

os.environ["APP_ENV"] = "test"

from app.config.settings import get_settings  # noqa: E402
from app.main import create_app  # noqa: E402


@pytest.fixture
def client() -> TestClient:
    get_settings.cache_clear()
    with TestClient(create_app()) as test_client:
        yield test_client
