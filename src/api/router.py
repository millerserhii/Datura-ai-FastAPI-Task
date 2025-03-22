from fastapi import APIRouter

from src.api.v1.endpoints import tao_dividends


api_router = APIRouter()

# Include endpoint routers
api_router.include_router(
    tao_dividends.router,
    prefix="/tao_dividends",
    tags=["Tao Dividends"],
)
