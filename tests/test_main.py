from unittest.mock import MagicMock, patch

from fastapi.testclient import TestClient

from peekguard.main import app

client = TestClient(app)

def test_read_root():
    response = client.get("/")
    assert response.status_code == 200
    assert response.json() == {"message": "Welcome to PeekGuard FastAPI!"}

@patch("peekguard.main.initialize_analyzer_engine")
def test_lifespan_startup_success(mock_initialize_analyzer_engine):
    mock_initialize_analyzer_engine.return_value = (MagicMock(), True)
    with TestClient(app) as c:
        assert c.app.state.service_initialized_successfully is True # type: ignore
        assert c.app.state.analyzer_engine is not None # type: ignore

@patch("peekguard.main.initialize_analyzer_engine")
def test_lifespan_startup_failure(mock_initialize_analyzer_engine):
    mock_initialize_analyzer_engine.return_value = (None, False)
    with TestClient(app) as c:
        assert c.app.state.service_initialized_successfully is False # type: ignore
        assert c.app.state.analyzer_engine is None # type: ignore

@patch("peekguard.main.initialize_analyzer_engine")
def test_lifespan_shutdown(mock_initialize_analyzer_engine):
    mock_initialize_analyzer_engine.return_value = (MagicMock(), True)
    with TestClient(app) as c:
        pass
    assert c.app.state.analyzer_engine is None # type: ignore
    assert c.app.state.service_initialized_successfully is False # type: ignore