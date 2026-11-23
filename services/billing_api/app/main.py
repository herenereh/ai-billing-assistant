import hmac

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse

from app.config import get_settings
from app.errors import error_body, register_error_handlers
from app.routers import v1

GATEWAY_HEADER = "X-Gateway-Secret"
# Reachable without the gateway: liveness check and the Swagger UI / OpenAPI document (no data).
OPEN_PATHS = {"/health", "/docs", "/docs/oauth2-redirect", "/openapi.json"}

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


@app.middleware("http")
async def require_gateway(request: Request, call_next):
    """In the cloud, only the API Gateway knows GATEWAY_SECRET and adds it as a header, so calls
    that bypass the gateway are rejected. Locally GATEWAY_SECRET is unset and this is a no-op."""
    secret = get_settings().gateway_secret
    if secret is not None and request.url.path not in OPEN_PATHS:
        sent = request.headers.get(GATEWAY_HEADER, "")
        if not hmac.compare_digest(sent.encode(), secret.get_secret_value().encode()):
            return JSONResponse(
                error_body("GATEWAY_REQUIRED", "Call this API through the API Gateway"), status_code=403
            )
    return await call_next(request)


@app.get("/health", tags=["Health"], summary="Liveness check")
def health():
    return {"status": "ok"}
