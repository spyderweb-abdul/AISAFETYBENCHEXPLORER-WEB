from fastapi.testclient import TestClient
from app.main import app

client = TestClient(app)


def test_list_benchmarks_returns_list():
    response = client.get("/benchmarks")
    assert response.status_code == 200
    assert isinstance(response.json(), list)
