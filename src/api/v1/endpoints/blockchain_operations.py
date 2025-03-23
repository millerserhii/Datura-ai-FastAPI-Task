from typing import Optional, List

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel, Field, PositiveFloat
from sqlalchemy.ext.asyncio import AsyncSession

from src.api.dependencies import get_api_key
from src.blockchain.models import DividendHistory, StakeTransaction
from src.blockchain.schemas import StakeOperation
from src.blockchain.service import get_blockchain_service
from src.database import get_session
from src.exceptions import BlockchainError


router = APIRouter()


class StakeRequest(BaseModel):
    """Request model for stake operation."""

    amount: PositiveFloat = Field(..., description="Amount of TAO to stake")
    netuid: Optional[int] = Field(None, description="Network UID (subnet ID)")
    hotkey: Optional[str] = Field(None, description="Account public key")


class UnstakeRequest(BaseModel):
    """Request model for unstake operation."""

    amount: PositiveFloat = Field(..., description="Amount of TAO to unstake")
    netuid: Optional[int] = Field(None, description="Network UID (subnet ID)")
    hotkey: Optional[str] = Field(None, description="Account public key")


@router.post(
    "/stake",
    response_model=StakeOperation,
    status_code=status.HTTP_200_OK,
    summary="Stake TAO to a hotkey",
    description=(
        "Stake the specified amount of TAO to a hotkey. "
        "If hotkey is omitted, uses the default hotkey. "
        "If netuid is omitted, uses the default netuid."
    ),
)
async def stake_tao(
    request: StakeRequest,
    _: str = Depends(get_api_key),
    session: AsyncSession = Depends(get_session),
) -> StakeOperation:
    """
    Stake TAO to a hotkey.

    Args:
        request: Stake request parameters
        _: API key (from dependency)
        session: Database session

    Returns:
        StakeOperation: Result of stake operation
    """
    try:
        service = await get_blockchain_service(session)
        result = await service.stake(
            amount=request.amount, hotkey=request.hotkey, netuid=request.netuid
        )

        if not result.success:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=result.error or "Stake operation failed",
            )

        return result
    except BlockchainError as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e),
        ) from e
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"An unexpected error occurred: {str(e)}",
        ) from e


@router.post(
    "/unstake",
    response_model=StakeOperation,
    status_code=status.HTTP_200_OK,
    summary="Unstake TAO from a hotkey",
    description=(
        "Unstake the specified amount of TAO from a hotkey. "
        "If hotkey is omitted, uses the default hotkey. "
        "If netuid is omitted, uses the default netuid."
    ),
)
async def unstake_tao(
    request: UnstakeRequest,
    _: str = Depends(get_api_key),
    session: AsyncSession = Depends(get_session),
) -> StakeOperation:
    """
    Unstake TAO from a hotkey.

    Args:
        request: Unstake request parameters
        _: API key (from dependency)
        session: Database session

    Returns:
        StakeOperation: Result of unstake operation
    """
    try:
        service = await get_blockchain_service(session)
        result = await service.unstake(
            amount=request.amount, hotkey=request.hotkey, netuid=request.netuid
        )

        if not result.success:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=result.error or "Unstake operation failed",
            )

        return result
    except BlockchainError as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e),
        ) from e
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"An unexpected error occurred: {str(e)}",
        ) from e


@router.get(
    "/dividend-history",
    response_model=List[DividendHistory],
    status_code=status.HTTP_200_OK,
    summary="Get dividend history",
    description=(
        "Retrieve dividend history for the specified netuid and hotkey. "
        "If netuid is omitted, returns data for all netuids. "
        "If hotkey is omitted, returns data for all hotkeys."
    ),
)
async def get_dividend_history(
    netuid: Optional[int] = Query(None, description="Network UID (subnet ID)"),
    hotkey: Optional[str] = Query(None, description="Account public key"),
    limit: int = Query(
        100, gt=0, le=1000, description="Maximum records to return"
    ),
    offset: int = Query(0, ge=0, description="Number of records to skip"),
    _: str = Depends(get_api_key),
    session: AsyncSession = Depends(get_session),
) -> list[DividendHistory]:
    """
    Get dividend history.

    Args:
        netuid: Filter by Network UID
        hotkey: Filter by hotkey
        limit: Maximum number of records to return
        offset: Number of records to skip
        _: API key (from dependency)
        session: Database session

    Returns:
        List[DividendHistory]: List of dividend history records
    """
    try:
        service = await get_blockchain_service(session)
        return await service.get_dividend_history(
            netuid=netuid,
            hotkey=hotkey,
            limit=limit,
            offset=offset,
        )
    except BlockchainError as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e),
        ) from e
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"An unexpected error occurred: {str(e)}",
        ) from e


@router.get(
    "/stake-transaction-history",
    response_model=List[StakeTransaction],
    status_code=status.HTTP_200_OK,
    summary="Get stake transaction history",
    description=(
        "Retrieve stake transaction history for the specified netuid and hotkey. "
        "Can also filter by operation type (stake or unstake)."
    ),
)
async def get_stake_transaction_history(
    netuid: Optional[int] = Query(None, description="Network UID (subnet ID)"),
    hotkey: Optional[str] = Query(None, description="Account public key"),
    operation_type: Optional[str] = Query(
        None, description="Operation type ('stake' or 'unstake')"
    ),
    limit: int = Query(
        100, gt=0, le=1000, description="Maximum records to return"
    ),
    offset: int = Query(0, ge=0, description="Number of records to skip"),
    _: str = Depends(get_api_key),
    session: AsyncSession = Depends(get_session),
) -> list[StakeTransaction]:
    """
    Get stake transaction history.

    Args:
        netuid: Filter by Network UID
        hotkey: Filter by hotkey
        operation_type: Filter by operation type ("stake" or "unstake")
        limit: Maximum number of records to return
        offset: Number of records to skip
        _: API key (from dependency)
        session: Database session

    Returns:
        List[StakeTransaction]: List of stake transactions
    """
    try:
        service = await get_blockchain_service(session)
        return await service.get_stake_transaction_history(
            netuid=netuid,
            hotkey=hotkey,
            operation_type=operation_type,
            limit=limit,
            offset=offset,
        )
    except BlockchainError as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e),
        ) from e
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"An unexpected error occurred: {str(e)}",
        ) from e
