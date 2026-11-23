"""Shared OpenAPI error response docs for v1 routes."""

ERROR_EXAMPLE = {"error": {"code": "BILL_NOT_FOUND", "message": "No bill for subscriber 5551001 for 2026-10."}}


def errors(*codes: int) -> dict:
    descriptions = {
        400: "Business rule violation",
        401: "Missing, invalid or expired token",
        403: "Authenticated but not allowed",
        404: "Subscriber or bill not found",
        409: "Duplicate transaction ID",
        422: "Request validation failed",
    }
    return {
        code: {"description": descriptions[code], "content": {"application/json": {"example": ERROR_EXAMPLE}}}
        for code in codes
    }
