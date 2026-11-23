USAGE = "/api/v1/usage"
CALC = "/api/v1/bills/calculate"
QUERY = "/api/v1/bills"


# --- Add Usage --------------------------------------------------------------

def test_add_phone_usage_records_10_minutes(client, admin_headers):
    resp = client.post(USAGE, headers=admin_headers,
                       json={"subscriberNo": "5551001", "month": 11, "year": 2026, "usageType": "PHONE"})
    assert resp.status_code == 201
    body = resp.json()
    assert body == {
        "transactionStatus": "SUCCESS", "subscriberNo": "5551001", "month": 11, "year": 2026,
        "usageType": "PHONE", "events": 1, "quantity": 10, "unit": "MIN",
    }


def test_add_internet_usage_with_count(client, admin_headers):
    resp = client.post(USAGE, headers=admin_headers, json={
        "subscriberNo": "5551001", "month": 11, "year": 2026, "usageType": "INTERNET", "count": 5})
    assert resp.status_code == 201
    assert (resp.json()["quantity"], resp.json()["unit"]) == (5, "MB")


def test_add_usage_requires_token(client):
    resp = client.post(USAGE, json={"subscriberNo": "5551001", "month": 11, "year": 2026, "usageType": "PHONE"})
    assert resp.status_code == 401
    assert resp.json()["error"]["code"] == "UNAUTHORIZED"


def test_add_usage_forbidden_for_subscriber(client, user1_headers):
    resp = client.post(USAGE, headers=user1_headers,
                       json={"subscriberNo": "5551001", "month": 11, "year": 2026, "usageType": "PHONE"})
    assert resp.status_code == 403


def test_add_usage_unknown_subscriber(client, admin_headers):
    resp = client.post(USAGE, headers=admin_headers,
                       json={"subscriberNo": "9999999", "month": 11, "year": 2026, "usageType": "PHONE"})
    assert resp.status_code == 404
    assert resp.json()["error"]["code"] == "SUBSCRIBER_NOT_FOUND"


def test_add_usage_validation(client, admin_headers):
    resp = client.post(USAGE, headers=admin_headers, json={
        "subscriberNo": "5551001", "month": 13, "year": 2026, "usageType": "SMS", "count": 0})
    assert resp.status_code == 422
    fields = {d["field"] for d in resp.json()["error"]["details"]}
    assert fields == {"month", "usageType", "count"}


# --- Calculate Bill ---------------------------------------------------------

def test_calculate_new_period_without_usage_is_internet_base(client, admin_headers):
    resp = client.post(CALC, headers=admin_headers, json={"subscriberNo": "5551001", "month": 1, "year": 2027})
    assert resp.status_code == 200
    bill = resp.json()["bill"]
    assert bill["total"] == 50.0
    assert bill["status"] == "UNPAID"
    assert bill["dueDate"] == "2027-02-15"


def test_calculate_crossing_block_boundary(client, admin_headers):
    # 100 phone events = 1,000 minutes (free), then one more event crosses into a paid block.
    base = {"subscriberNo": "5551002", "month": 12, "year": 2026, "usageType": "PHONE"}
    client.post(USAGE, headers=admin_headers, json={**base, "count": 100})
    calc_body = {"subscriberNo": "5551002", "month": 12, "year": 2026}
    assert client.post(CALC, headers=admin_headers, json=calc_body).json()["bill"]["total"] == 50.0

    client.post(USAGE, headers=admin_headers, json={**base, "count": 1})
    assert client.post(CALC, headers=admin_headers, json=calc_body).json()["bill"]["total"] == 60.0


def test_recalculation_keeps_paid_amount(client, admin_headers):
    # 5551002 Oct 2026: $80 with $30 already paid. Push internet over 30 GB → $90.
    client.post(USAGE, headers=admin_headers, json={
        "subscriberNo": "5551002", "month": 10, "year": 2026, "usageType": "INTERNET", "count": 10_000})
    bill = client.post(CALC, headers=admin_headers,
                       json={"subscriberNo": "5551002", "month": 10, "year": 2026}).json()["bill"]
    assert bill["total"] == 90.0
    assert bill["paidAmount"] == 30.0
    assert bill["remainingBalance"] == 60.0
    assert bill["status"] == "PARTIAL"


def test_calculate_forbidden_for_subscriber(client, user1_headers):
    resp = client.post(CALC, headers=user1_headers, json={"subscriberNo": "5551001", "month": 10, "year": 2026})
    assert resp.status_code == 403


def test_calculate_unknown_subscriber(client, admin_headers):
    resp = client.post(CALC, headers=admin_headers, json={"subscriberNo": "9999999", "month": 10, "year": 2026})
    assert resp.status_code == 404


# --- Query Bill (public) ----------------------------------------------------

def test_query_bill_success_without_token(client):
    resp = client.get(QUERY, params={"subscriberNo": "5551001", "month": 10, "year": 2026})
    assert resp.status_code == 200
    assert resp.json() == {
        "subscriberNo": "5551001", "month": 10, "year": 2026, "total": 80.0, "paidAmount": 0.0,
        "remainingBalance": 80.0, "status": "UNPAID", "dueDate": "2026-11-15",
    }


def test_query_paid_bill(client):
    body = client.get(QUERY, params={"subscriberNo": "5551001", "month": 9, "year": 2026}).json()
    assert (body["total"], body["remainingBalance"], body["status"]) == (50.0, 0.0, "PAID")


def test_query_bill_not_calculated(client):
    resp = client.get(QUERY, params={"subscriberNo": "5551001", "month": 4, "year": 2025})
    assert resp.status_code == 404
    assert resp.json()["error"]["code"] == "BILL_NOT_FOUND"


def test_query_bill_validation(client):
    resp = client.get(QUERY, params={"subscriberNo": "5551001", "month": 0, "year": 2026})
    assert resp.status_code == 422


def test_query_bill_missing_params(client):
    resp = client.get(QUERY)
    assert resp.status_code == 422
    assert {d["field"] for d in resp.json()["error"]["details"]} == {"subscriberNo", "month", "year"}
