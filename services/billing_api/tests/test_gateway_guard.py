"""Direct calls that bypass the API Gateway are rejected when GATEWAY_SECRET is configured."""

import pytest
from pydantic import SecretStr

from app.config import get_settings

QUERY = "/api/v1/bills?subscriberNo=5551001&month=10&year=2026"


@pytest.fixture
def gateway_secret(monkeypatch):
    monkeypatch.setattr(get_settings(), "gateway_secret", SecretStr("gw-secret-123"))


def test_no_secret_configured_allows_direct_calls(client):
    assert client.get(QUERY).status_code == 200


def test_direct_call_without_header_is_rejected(client, gateway_secret):
    resp = client.get(QUERY)
    assert resp.status_code == 403
    assert resp.json()["error"]["code"] == "GATEWAY_REQUIRED"


def test_wrong_header_is_rejected(client, gateway_secret):
    assert client.get(QUERY, headers={"X-Gateway-Secret": "guess"}).status_code == 403


def test_call_through_gateway_is_allowed(client, gateway_secret):
    assert client.get(QUERY, headers={"X-Gateway-Secret": "gw-secret-123"}).status_code == 200


@pytest.mark.parametrize("path", ["/health", "/docs", "/openapi.json"])
def test_health_and_docs_stay_open(client, gateway_secret, path):
    assert client.get(path).status_code == 200
