from fastapi import APIRouter

from app.routers.v1 import auth, bills, payments, usage

router = APIRouter(prefix="/api/v1")
router.include_router(auth.router)
router.include_router(usage.router)
router.include_router(bills.router)
router.include_router(payments.router)
