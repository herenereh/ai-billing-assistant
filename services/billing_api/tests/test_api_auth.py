from datetime import UTC, datetime, timedelta

import jwt

from app.auth import AUDIENCE, ISSUER
from app.config import get_settings

LOGIN = "/api/v1/auth/login"
DETAILED = "/api/v1/bills/detailed?month=10&year=2026"


def test_login_success_returns_bearer_token(client):
    resp = client.post(LOGIN, json={"subscriberNo": "5551001", "password": "Demo#1001"})
    assert resp.status_code == 200
    body = resp.json()
    assert body["tokenType"] == "Bearer"
    assert body["expiresIn"] == get_settings().jwt_expire_minutes * 60
    claims = jwt.decode(body["accessToken"], get_settings().jwt_secret, algorithms=["HS256"], audience=AUDIENCE)
    assert claims["sub"] == "5551001"
    assert claims["role"] == "SUBSCRIBER"


def test_login_wrong_password(client):
    resp = client.post(LOGIN, json={"subscriberNo": "5551001", "password": "wrong"})
    assert resp.status_code == 401
    assert resp.json()["error"]["code"] == "INVALID_CREDENTIALS"


def test_login_unknown_subscriber_same_error(client):
    resp = client.post(LOGIN, json={"subscriberNo": "9999999", "password": "Demo#1001"})
    assert resp.status_code == 401
    assert resp.json()["error"]["code"] == "INVALID_CREDENTIALS"


def test_login_validation_error(client):
    resp = client.post(LOGIN, json={"subscriberNo": "55-51", "password": ""})
    assert resp.status_code == 422
    err = resp.json()["error"]
    assert err["code"] == "VALIDATION_ERROR"
    assert {d["field"] for d in err["details"]} == {"subscriberNo", "password"}


def _token(**overrides):
    now = datetime.now(UTC)
    claims = {"sub": "5551001", "role": "SUBSCRIBER", "iss": ISSUER, "aud": AUDIENCE,
              "iat": now, "exp": now + timedelta(minutes=5)}
    claims.update(overrides)
    secret = claims.pop("_secret", get_settings().jwt_secret)
    return {"Authorization": f"Bearer {jwt.encode(claims, secret, algorithm='HS256')}"}


def test_expired_token_rejected(client):
    resp = client.get(DETAILED, headers=_token(exp=datetime.now(UTC) - timedelta(seconds=1)))
    assert resp.status_code == 401
    assert resp.json()["error"]["message"] == "Token has expired"


def test_token_signed_with_other_key_rejected(client):
    resp = client.get(DETAILED, headers=_token(_secret="attacker-secret-attacker-secret-123"))
    assert resp.status_code == 401
    assert resp.json()["error"]["message"] == "Invalid token"


def test_token_with_wrong_audience_rejected(client):
    assert client.get(DETAILED, headers=_token(aud="someone-else")).status_code == 401


def test_token_with_unknown_role_rejected(client):
    assert client.get(DETAILED, headers=_token(role="SUPERUSER")).status_code == 401


def test_malformed_authorization_header(client):
    resp = client.get(DETAILED, headers={"Authorization": "Bearer not-a-jwt"})
    assert resp.status_code == 401
