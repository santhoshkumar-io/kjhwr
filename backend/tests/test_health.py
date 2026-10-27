"""Tests for the Phase 3 health endpoint.

Small, but they pin the two things that make deployment work and that are easy to
break later: the /api prefix on the route, and the fact that this app owns its own
404 because routing into a Vercel service is final.
"""

from __future__ import annotations

from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)


def test_health_reports_the_real_row_counts():
    """A health check that cannot be wrong proves nothing, so it returns real data."""
    response = client.get("/api/health")

    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "ok"
    assert body["actual_rows"] == 1488
    assert body["forecast_rows"] == 19856


def test_health_reports_the_delivery_window():
    body = client.get("/api/health").json()

    assert body["delivery_from"] == "2026-01-02T00:00:00Z"
    assert body["delivery_to"] == "2026-02-01T23:30:00Z"


def test_the_route_carries_the_api_prefix():
    """On Vercel the service receives the ORIGINAL path, so /api must be part of it.

    If someone 'tidies' this to /health, local Docker keeps working through the Vite
    proxy only if the proxy is also changed, and production 404s. Pin it.
    """
    assert client.get("/api/health").status_code == 200
    assert client.get("/health").status_code == 404


def test_unknown_paths_return_our_own_json_404():
    """Routing into a service is final - Vercel will not fall back to another rewrite."""
    response = client.get("/api/does-not-exist")

    assert response.status_code == 404
    assert response.json()["error"] == "Not found"


def test_errors_do_not_leak_a_file_path_or_traceback():
    """Phase 8 checks this properly, but there is no reason to write it wrongly first."""
    body = client.get("/api/does-not-exist").text

    assert "Traceback" not in body
    assert "/srv" not in body
    assert ".py" not in body
