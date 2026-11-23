from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.orm import Session

from app import schemas
from app.auth import create_access_token, verify_password
from app.db import get_db
from app.errors import ApiError
from app.models import Subscriber
from app.routers.v1.common import errors

router = APIRouter(prefix="/auth", tags=["Authentication"])


@router.post(
    "/login",
    response_model=schemas.TokenResponse,
    summary="Log in and receive a JWT",
    responses=errors(401, 422),
)
def login(req: schemas.LoginRequest, db: Session = Depends(get_db)):
    sub = db.scalar(select(Subscriber).where(Subscriber.subscriber_no == req.subscriber_no))
    if sub is None or not verify_password(req.password, sub.password_hash):
        raise ApiError(401, "INVALID_CREDENTIALS", "Invalid subscriber number or password")
    token, expires_in = create_access_token(sub.subscriber_no, sub.role)
    return schemas.TokenResponse(access_token=token, expires_in=expires_in)
