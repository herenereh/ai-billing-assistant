"""In-memory fakes: a Billing API (behind httpx.MockTransport) and a documentation search."""

from __future__ import annotations

import json
from datetime import date

import httpx

GUIDE_SECTIONS = {
    "2.1": ("Included minutes", "The first 1,000 minutes of phone calls in a billing month are free."),
    "2.2": ("Additional minutes", "Each additional 1,000-minute block costs $10."),
    "3.1": ("Included internet allowance", "Internet access costs $50 per month for up to 20 GB."),
    "3.2": ("Additional internet blocks", "Each additional 10 GB block costs $10."),
    "5.1": ("Full and partial payments", "Subscribers may make full or partial payments."),
    "6.2": ("Late payment reminder", "An unpaid bill may trigger a reminder after its due date."),
    "8.1": ("What is the cost of extra internet?", "Each additional 10 GB block beyond 20 GB costs $10."),
}


class FakeDocs:
    def __init__(self):
        self.queries: list[str] = []
        self.fail = False

    async def search(self, query: str, top_k: int = 3) -> dict:
        from billing_agent.docs_client import DocsError

        self.queries.append(query)
        if self.fail:
            raise DocsError("documentation service unavailable")
        q = query.lower()
        if "weather" in q:
            sections = []
        elif "internet" in q and "minutes" in q:
            sections = ["3.2", "2.2", "3.1", "2.1"]
        elif "internet" in q:
            sections = ["8.1", "3.2"]
        elif "part" in q:
            sections = ["5.1"]
        elif "late" in q:
            sections = ["6.2"]
        else:
            sections = ["2.1"]
        return {
            "document": "Mobile_Provider_Billing_Guide.md",
            "document_id": "MOB-BILLING-2026-01",
            "query": query,
            "matches": [
                {"section": s, "heading": GUIDE_SECTIONS[s][0], "parent_heading": "", "text": GUIDE_SECTIONS[s][1],
                 "score": 1.0}
                for s in sections[:top_k]
            ],
        }


class FakeBillingApi:
    """Mimics the real API's routes, auth and error format."""

    def __init__(self):
        self.users = {"5551001": "pw1", "5551002": "pw2"}
        self.bills = {
            ("5551001", 2026, 9): dict(minutes=800, mb=18_000, phone=0, internet=50, total=50, paid=50),
            ("5551001", 2026, 10): dict(minutes=1_350, mb=35_000, phone=10, internet=70, total=80, paid=0),
            ("5551002", 2026, 10): dict(minutes=500, mb=12_000, phone=0, internet=50, total=50, paid=0),
        }
        self.transactions: set[str] = set()
        self.requests: list[httpx.Request] = []
        self.drop_next_payment_response = False  # simulate a lost response after the payment is stored

    def transport(self) -> httpx.MockTransport:
        return httpx.MockTransport(self.handle)

    @staticmethod
    def _err(status: int, code: str, message: str) -> httpx.Response:
        return httpx.Response(status, json={"error": {"code": code, "message": message}})

    def _subscriber(self, request: httpx.Request) -> str | None:
        auth = request.headers.get("Authorization", "")
        return auth.removeprefix("Bearer tok-") if auth.startswith("Bearer tok-") else None

    def _summary(self, no: str, year: int, month: int) -> dict:
        b = self.bills[(no, year, month)]
        status = "PAID" if b["paid"] >= b["total"] else "PARTIAL" if b["paid"] > 0 else "UNPAID"
        return {"subscriberNo": no, "month": month, "year": year, "total": float(b["total"]),
                "paidAmount": float(b["paid"]), "remainingBalance": float(b["total"] - b["paid"]),
                "status": status, "dueDate": date(year, month % 12 + 1, 15).isoformat()}

    def handle(self, request: httpx.Request) -> httpx.Response:
        self.requests.append(request)
        path, params = request.url.path, request.url.params
        if path == "/api/v1/auth/login":
            body = json.loads(request.content)
            if self.users.get(body["subscriberNo"]) != body["password"]:
                return self._err(401, "INVALID_CREDENTIALS", "Invalid subscriber number or password")
            return httpx.Response(200, json={"accessToken": f"tok-{body['subscriberNo']}", "tokenType": "Bearer",
                                             "expiresIn": 3600})
        if path == "/api/v1/bills":
            key = (params["subscriberNo"], int(params["year"]), int(params["month"]))
            if key not in self.bills:
                return self._err(404, "BILL_NOT_FOUND", "No bill for that period")
            return httpx.Response(200, json=self._summary(*key))

        subscriber = self._subscriber(request)
        if subscriber is None:
            return self._err(401, "UNAUTHORIZED", "Missing bearer token")
        if path == "/api/v1/bills/detailed":
            key = (subscriber, int(params["year"]), int(params["month"]))
            if key not in self.bills:
                return self._err(404, "BILL_NOT_FOUND", "No bill for that period")
            b = self.bills[key]
            return httpx.Response(200, json={
                **self._summary(*key),
                "usage": {"phoneMinutes": b["minutes"], "internetMb": b["mb"], "internetGb": b["mb"] / 1000},
                "charges": {"phoneCharge": float(b["phone"]), "internetCharge": float(b["internet"]),
                            "total": float(b["total"])},
                "usageRecords": {"items": [], "page": 1, "pageSize": 20, "totalItems": 0, "totalPages": 0},
            })
        if path == "/api/v1/payments":
            body = json.loads(request.content)
            if body["transactionId"] in self.transactions:
                return self._err(409, "DUPLICATE_TRANSACTION", "Transaction was already processed")
            key = (subscriber, body["year"], body["month"])
            if key not in self.bills:
                return self._err(404, "BILL_NOT_FOUND", "No bill for that period")
            b = self.bills[key]
            if body["amount"] > b["total"] - b["paid"]:
                return self._err(400, "INVALID_PAYMENT", "payment amount exceeds remaining balance")
            b["paid"] += body["amount"]
            self.transactions.add(body["transactionId"])
            if self.drop_next_payment_response:
                self.drop_next_payment_response = False
                raise httpx.ReadTimeout("response lost", request=request)
            s = self._summary(*key)
            return httpx.Response(201, json={"paymentStatus": "SUCCESS", "transactionId": body["transactionId"],
                                             "amount": body["amount"], "paidAmount": s["paidAmount"],
                                             "remainingBalance": s["remainingBalance"], "billStatus": s["status"]})
        return self._err(404, "NOT_FOUND", "Not Found")

    def payment_requests(self) -> list[dict]:
        return [json.loads(r.content) for r in self.requests if r.url.path == "/api/v1/payments"]
