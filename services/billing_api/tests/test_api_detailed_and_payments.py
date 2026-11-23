DETAILED = "/api/v1/bills/detailed"
PAY = "/api/v1/payments"
QUERY = "/api/v1/bills"


# --- Query Bill Detailed ----------------------------------------------------

def test_detailed_breakdown_for_own_bill(client, user1_headers):
    resp = client.get(DETAILED, headers=user1_headers, params={"month": 10, "year": 2026})
    assert resp.status_code == 200
    body = resp.json()
    assert body["usage"] == {"phoneMinutes": 1350, "internetMb": 35000, "internetGb": 35.0}
    assert body["charges"] == {"phoneCharge": 10.0, "internetCharge": 70.0, "total": 80.0}
    assert body["remainingBalance"] == 80.0
    page = body["usageRecords"]
    assert (page["page"], page["pageSize"], page["totalItems"], page["totalPages"]) == (1, 10, 16, 2)
    assert len(page["items"]) == 10


def test_detailed_paging(client, user1_headers):
    params = {"month": 10, "year": 2026, "pageSize": 5}
    pages = [client.get(DETAILED, headers=user1_headers, params={**params, "page": p}).json()["usageRecords"]
             for p in (1, 4, 5)]
    assert pages[0]["totalPages"] == 4
    assert len(pages[0]["items"]) == 5
    assert len(pages[1]["items"]) == 1           # 16 records → last page has 1
    assert pages[2]["items"] == []               # beyond the last page
    ids = [i["id"] for p in (1, 2, 3, 4)
           for i in client.get(DETAILED, headers=user1_headers, params={**params, "page": p}).json()["usageRecords"]["items"]]
    assert len(ids) == len(set(ids)) == 16       # no overlap or gaps between pages


def test_detailed_requires_token(client):
    resp = client.get(DETAILED, params={"month": 10, "year": 2026})
    assert resp.status_code == 401


def test_detailed_cannot_read_another_subscriber(client, user1_headers):
    resp = client.get(DETAILED, headers=user1_headers, params={"month": 10, "year": 2026, "subscriberNo": "5551002"})
    assert resp.status_code == 403
    assert resp.json()["error"]["message"] == "You can only view your own bill"


def test_detailed_admin_can_read_any_subscriber(client, admin_headers):
    resp = client.get(DETAILED, headers=admin_headers, params={"month": 10, "year": 2026, "subscriberNo": "5551002"})
    assert resp.status_code == 200
    assert resp.json()["subscriberNo"] == "5551002"


def test_detailed_bill_not_found(client, user1_headers):
    resp = client.get(DETAILED, headers=user1_headers, params={"month": 4, "year": 2025})
    assert resp.status_code == 404


def test_detailed_invalid_paging(client, user1_headers):
    for bad in ({"page": 0}, {"pageSize": 0}, {"pageSize": 101}):
        resp = client.get(DETAILED, headers=user1_headers, params={"month": 10, "year": 2026, **bad})
        assert resp.status_code == 422, bad


# --- Pay Bill ---------------------------------------------------------------

def _pay(client, headers, amount, tx, month=10, year=2026):
    return client.post(PAY, headers=headers,
                       json={"month": month, "year": year, "amount": amount, "transactionId": tx})


def test_partial_then_full_payment(client, user1_headers):
    first = _pay(client, user1_headers, 30, "tx-test-0001")
    assert first.status_code == 201
    assert first.json() == {"paymentStatus": "SUCCESS", "transactionId": "tx-test-0001", "amount": 30.0,
                            "paidAmount": 30.0, "remainingBalance": 50.0, "billStatus": "PARTIAL"}

    second = _pay(client, user1_headers, 50, "tx-test-0002")
    assert second.status_code == 201
    assert (second.json()["remainingBalance"], second.json()["billStatus"]) == (0.0, "PAID")

    stored = client.get(QUERY, params={"subscriberNo": "5551001", "month": 10, "year": 2026}).json()
    assert (stored["paidAmount"], stored["status"]) == (80.0, "PAID")


def test_duplicate_transaction_id_rejected_and_balance_preserved(client, user1_headers):
    assert _pay(client, user1_headers, 20, "tx-dup-0001").status_code == 201
    dup = _pay(client, user1_headers, 20, "tx-dup-0001")
    assert dup.status_code == 409
    assert dup.json()["error"]["code"] == "DUPLICATE_TRANSACTION"
    stored = client.get(QUERY, params={"subscriberNo": "5551001", "month": 10, "year": 2026}).json()
    assert stored["paidAmount"] == 20.0


def test_duplicate_transaction_id_across_subscribers(client, user1_headers, user2_headers):
    assert _pay(client, user1_headers, 10, "tx-shared-01").status_code == 201
    assert _pay(client, user2_headers, 10, "tx-shared-01").status_code == 409


def test_overpayment_rejected(client, user2_headers):
    # 5551002 owes $50 of $80.
    resp = _pay(client, user2_headers, 50.01, "tx-over-0001")
    assert resp.status_code == 400
    assert resp.json()["error"]["code"] == "INVALID_PAYMENT"
    assert "exceeds remaining balance of 50.00" in resp.json()["error"]["message"]


def test_paying_already_paid_bill_rejected(client, user1_headers):
    resp = _pay(client, user1_headers, 1, "tx-paid-0001", month=9)
    assert resp.status_code == 400
    assert "already fully paid" in resp.json()["error"]["message"]


def test_payment_requires_token(client):
    resp = client.post(PAY, json={"month": 10, "year": 2026, "amount": 10, "transactionId": "tx-noauth-1"})
    assert resp.status_code == 401


def test_payment_for_missing_bill(client, user1_headers):
    resp = _pay(client, user1_headers, 10, "tx-missing-1", month=4, year=2025)
    assert resp.status_code == 404


def test_payment_validation(client, user1_headers):
    for amount, tx in ((0, "tx-valid-01"), (-5, "tx-valid-02"), (10.001, "tx-valid-03"), (10, "bad id!")):
        resp = _pay(client, user1_headers, amount, tx)
        assert resp.status_code == 422, (amount, tx)


def test_payment_always_applies_to_token_owner(client, user1_headers):
    # A subscriberNo in the body is ignored: identity comes only from the JWT.
    resp = client.post(PAY, headers=user1_headers, json={
        "month": 10, "year": 2026, "amount": 10, "transactionId": "tx-owner-01", "subscriberNo": "5551002"})
    assert resp.status_code == 201
    user1 = client.get(QUERY, params={"subscriberNo": "5551001", "month": 10, "year": 2026}).json()
    user2 = client.get(QUERY, params={"subscriberNo": "5551002", "month": 10, "year": 2026}).json()
    assert user1["paidAmount"] == 10.0
    assert user2["paidAmount"] == 30.0   # unchanged seed value


# --- Misc -------------------------------------------------------------------

def test_health(client):
    assert client.get("/health").json() == {"status": "ok"}


def test_unknown_route_uses_error_format(client):
    resp = client.get("/api/v1/nope")
    assert resp.status_code == 404
    assert resp.json()["error"]["code"] == "NOT_FOUND"


def test_openapi_lists_versioned_routes(client):
    paths = client.get("/openapi.json").json()["paths"]
    assert {"/api/v1/auth/login", "/api/v1/usage", "/api/v1/bills/calculate", "/api/v1/bills",
            "/api/v1/bills/detailed", "/api/v1/payments"} <= set(paths)
