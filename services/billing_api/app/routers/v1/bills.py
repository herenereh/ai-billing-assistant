from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app import schemas
from app.auth import Principal, get_current_principal, require_admin
from app.db import get_db
from app.errors import ApiError
from app.routers.v1.common import errors
from app.services import bill_service

router = APIRouter(prefix="/bills", tags=["Bills"])

# Query-parameter constraints (Annotated Field constraints are not applied to Query params).
MONTH = {"ge": 1, "le": 12, "examples": [10]}
YEAR = {"ge": 2000, "le": 2100, "examples": [2026]}
SUBSCRIBER_NO = {"min_length": 3, "max_length": 20, "pattern": r"^[A-Za-z0-9]+$", "examples": ["5551001"]}


@router.post(
    "/calculate",
    response_model=schemas.CalculateBillResponse,
    summary="Calculate Bill (admin)",
    description="Totals recorded usage for the period, applies the pricing rules and stores the bill. "
    "Recalculation keeps any amount already paid.",
    responses=errors(401, 403, 404, 422),
)
def calculate_bill(
    req: schemas.CalculateBillRequest,
    db: Session = Depends(get_db),
    _: Principal = Depends(require_admin),
):
    return bill_service.calculate_bill(db, req)


@router.get(
    "",
    response_model=schemas.BillSummary,
    summary="Query Bill (no auth)",
    description="Bill total, paid amount, remaining balance and status. Public per the Mobile Provider App spec.",
    responses=errors(404, 422),
)
def query_bill(
    subscriber_no: str = Query(alias="subscriberNo", **SUBSCRIBER_NO),
    month: int = Query(**MONTH),
    year: int = Query(**YEAR),
    db: Session = Depends(get_db),
):
    return bill_service.query_bill(db, subscriber_no, year, month)


@router.get(
    "/detailed",
    response_model=schemas.BillDetailed,
    summary="Query Bill Detailed (auth, paged)",
    description="Totals, usage and charge breakdown, plus a page of usage records. Subscribers see only "
    "their own bill (identity from the JWT). Admins may pass subscriberNo.",
    responses=errors(401, 403, 404, 422),
)
def query_bill_detailed(
    month: int = Query(**MONTH),
    year: int = Query(**YEAR),
    page: int = Query(1, ge=1),
    page_size: int = Query(10, ge=1, le=100, alias="pageSize"),
    subscriber_no: str | None = Query(None, alias="subscriberNo", **SUBSCRIBER_NO),
    db: Session = Depends(get_db),
    principal: Principal = Depends(get_current_principal),
):
    target = subscriber_no or principal.subscriber_no
    if target != principal.subscriber_no and not principal.is_admin:
        raise ApiError(403, "FORBIDDEN", "You can only view your own bill")
    return bill_service.query_bill_detailed(db, target, year, month, page, page_size)
