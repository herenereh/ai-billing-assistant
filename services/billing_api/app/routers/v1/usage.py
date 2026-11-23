from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app import schemas
from app.auth import Principal, require_admin
from app.db import get_db
from app.routers.v1.common import errors
from app.services import bill_service

router = APIRouter(prefix="/usage", tags=["Usage"])


@router.post(
    "",
    response_model=schemas.AddUsageResponse,
    status_code=201,
    summary="Add Usage (admin)",
    description="Records usage events. Each PHONE event adds 10 minutes; each INTERNET event adds 1 MB.",
    responses=errors(401, 403, 404, 422),
)
def add_usage(
    req: schemas.AddUsageRequest,
    db: Session = Depends(get_db),
    _: Principal = Depends(require_admin),
):
    return bill_service.add_usage(db, req)
