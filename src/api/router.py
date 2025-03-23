from fastapi import APIRouter

from src.api.v1.endpoints import blockchain_operations, tao_dividends


api_router = APIRouter()

# Include endpoint routers
api_router.include_router(
    tao_dividends.router,
    prefix="/tao_dividends",
    tags=["Tao Dividends"],
)

api_router.include_router(
    blockchain_operations.router,
    prefix="/blockchain",
    tags=["Blockchain Operations"],
)
