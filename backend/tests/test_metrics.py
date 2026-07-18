from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)


def test_list_metrics_for_nonexistent_benchmark_returns_404():
    fake_id = "00000000-0000-0000-0000-000000000000"
    response = client.get(f"/benchmarks/{fake_id}/metrics")
    assert response.status_code == 404


def test_completeness_check_for_nonexistent_benchmark_returns_404():
    fake_id = "00000000-0000-0000-0000-000000000000"
    response = client.get(f"/benchmarks/{fake_id}/metrics/completeness")
    assert response.status_code == 404


def test_get_nonexistent_metric_returns_404():
    fake_id = "00000000-0000-0000-0000-000000000000"
    response = client.get(f"/metrics/{fake_id}")
    assert response.status_code == 404


def test_create_metric_requires_admin_auth():
    fake_id = "00000000-0000-0000-0000-000000000000"
    payload = {
        "benchmark_id": fake_id,
        "benchmark_name": "TestBench",
        "paper_title": "A Test Paper",
        "metric_name": "Attack Success Rate",
    }
    response = client.post(f"/benchmarks/{fake_id}/metrics", json=payload)
    assert response.status_code == 401


def test_update_metric_requires_admin_auth():
    fake_id = "00000000-0000-0000-0000-000000000000"
    response = client.patch(f"/metrics/{fake_id}", json={"metric_name": "New Name"})
    assert response.status_code == 401


def test_delete_metric_requires_admin_auth():
    fake_id = "00000000-0000-0000-0000-000000000000"
    response = client.delete(f"/metrics/{fake_id}")
    assert response.status_code == 401
