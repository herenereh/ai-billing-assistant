"""HTTP client for the Billing REST API (through the API Gateway in the cloud).

Every call after login carries the logged-in user's JWT. The client never takes a subscriber
number for protected calls: the API derives identity from the token.
"""

from __future__ import annotations

from decimal import Decimal
from typing import Any

import httpx


class ApiError(Exception):
    """The API answered with an error status (4xx/5xx)."""

    def __init__(self, status: int, code: str, message: str):
        super().__init__(f"{status} {code}: {message}")
        self.status = status
        self.code = code
        self.message = message


class ApiUnavailable(Exception):
    """The API could not be reached (network error or timeout). Safe to retry idempotent calls."""


class BillingApiClient:
    def __init__(
        self,
        base_url: str,
        *,
        subscription_key: str | None = None,
        timeout: float = 15.0,
        transport: httpx.AsyncBaseTransport | None = None,
    ):
        headers = {"Accept": "application/json"}
        if subscription_key:
            headers["Ocp-Apim-Subscription-Key"] = subscription_key
        self._http = httpx.AsyncClient(
            base_url=base_url.rstrip("/") + "/", headers=headers, timeout=timeout, transport=transport
        )
        self._token: str | None = None

    async def aclose(self) -> None:
        await self._http.aclose()

    @property
    def is_authenticated(self) -> bool:
        return self._token is not None

    def logout(self) -> None:
        self._token = None

    async def _request(self, method: str, path: str, *, auth: bool, **kwargs: Any) -> dict:
        headers = {}
        if auth:
            if self._token is None:
                raise ApiError(401, "NOT_LOGGED_IN", "Log in first")
            headers["Authorization"] = f"Bearer {self._token}"
        try:
            resp = await self._http.request(method, path, headers=headers, **kwargs)
        except httpx.TransportError as exc:
            raise ApiUnavailable(str(exc) or exc.__class__.__name__) from exc
        if resp.is_success:
            return resp.json()
        try:
            err = resp.json()["error"]
            raise ApiError(resp.status_code, err.get("code", "ERROR"), err.get("message", resp.reason_phrase))
        except (ValueError, KeyError, TypeError):
            raise ApiError(resp.status_code, "HTTP_ERROR", resp.text[:200] or resp.reason_phrase)

    async def login(self, subscriber_no: str, password: str) -> None:
        body = await self._request(
            "POST", "auth/login", auth=False, json={"subscriberNo": subscriber_no, "password": password}
        )
        self._token = body["accessToken"]

    async def query_bill(self, subscriber_no: str, month: int, year: int) -> dict:
        # Public per the spec, but the agent only ever passes the logged-in user's own number.
        return await self._request(
            "GET", "bills", auth=False, params={"subscriberNo": subscriber_no, "month": month, "year": year}
        )

    async def query_bill_detailed(self, month: int, year: int, page: int = 1, page_size: int = 20) -> dict:
        return await self._request(
            "GET", "bills/detailed", auth=True,
            params={"month": month, "year": year, "page": page, "pageSize": page_size},
        )

    async def pay_bill(self, month: int, year: int, amount: Decimal, transaction_id: str) -> dict:
        return await self._request(
            "POST", "payments", auth=True,
            json={"month": month, "year": year, "amount": float(amount), "transactionId": transaction_id},
        )
