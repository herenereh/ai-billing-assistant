from fastapi import FastAPI

from app.errors import register_error_handlers
from app.routers import v1

API_DESCRIPTION = """
Billing REST API for the fictitious mobile provider (SE4458 midterm, Group 2).

* Versioned under `/api/v1`; a future `/api/v2` can run side by side.
* Authenticate with `POST /api/v1/auth/login`, then send `Authorization: Bearer <token>`.
* Errors always look like `{"error": {"code": "...", "message": "..."}}`.
* Pricing rules: Mobile_Provider_Billing_Guide.md (MOB-BILLING-2026-01).
"""

app = FastAPI(
    title="Mobile Provider Billing API",
    version="1.0.0",
    description=API_DESCRIPTION,
)
register_error_handlers(app)
app.include_router(v1.router)


@app.get("/health", tags=["Health"], summary="Liveness check")
def health():
    return {"status": "ok"}
