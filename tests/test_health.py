"""
Tests for PostVisit AI Health & Root Metadata Endpoints.
Verifies rapid response without loading ML models.
"""

import pytest
from fastapi.testclient import TestClient
from api.main import app

client = TestClient(app)


def test_health_check_endpoint():
    """Verify GET /health returns 200 OK with correct status and service name."""
    response = client.get("/health")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "ok"
    assert data["service"] == "PostVisit AI API"
    assert "version" in data


def test_root_endpoint():
    """Verify GET / returns 200 OK with API information and docs links."""
    response = client.get("/")
    assert response.status_code == 200
    data = response.json()
    assert data["name"] == "PostVisit AI"
    assert data["description"] == "Clinical consultation processing API"
    assert data["docs"] == "/docs"
    assert data["health"] == "/health"
    assert "version" in data


def test_openapi_docs_endpoint():
    """Verify Swagger UI and OpenAPI schema are accessible."""
    docs_resp = client.get("/docs")
    assert docs_resp.status_code == 200

    openapi_resp = client.get("/openapi.json")
    assert openapi_resp.status_code == 200
    openapi_data = openapi_resp.json()
    assert "/api/v1/consultations/process" in openapi_data["paths"]
