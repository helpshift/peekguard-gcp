from unittest.mock import MagicMock

import pytest
from fastapi.testclient import TestClient

from peekguard.main import app


@pytest.fixture
def client():
    with TestClient(app) as c:
        app.state.analyzer_engine = MagicMock()
        app.state.service_initialized_successfully = True
        yield c

def test_health_check(client):
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json()["status"] == "healthy"