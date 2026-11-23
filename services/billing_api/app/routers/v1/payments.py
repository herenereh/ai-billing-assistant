from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app import schemas
from app.auth import Principal, get_current_principal
from app.db import get_db
from app.routers.v1.common import errors
from app.services import bill_service

router = APIRouter(prefix="/payments", tags=["Payments"])


@router.post(
    "",
    response_model=schemas.PayBillResponse,
    status_code=201,
    summary="Pay Bill (auth)",
    description="Records a simulated full or partial payment for the caller's own bill. "
    "Duplicate transaction IDs are rejected with 409. No real card processing.",
    responses=errors(400, 401, 404, 409, 422),
)
def pay_bill(
    req: schemas.PayBillRequest,
    db: Session = Depends(get_db),
    principal: Principal = Depends(get_current_principal),
):
    return bill_service.pay_bill(db, principal.subscriber_no, req)
