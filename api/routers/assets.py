"""Assets router"""
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from typing import List

from core.database import get_db
from models import Asset
from schemas import AssetResponse

router = APIRouter()


@router.get("", response_model=List[AssetResponse])
async def get_assets(
    asset_type: str = None,
    active: bool = None,
    db: AsyncSession = Depends(get_db)
):
    """Get all assets"""
    query = select(Asset)

    if asset_type:
        query = query.where(Asset.type == asset_type)
    
    if active is not None:
        query = query.where(Asset.is_active == active)

    result = await db.execute(query)
    assets = result.scalars().all()

    return [
        AssetResponse(
            id=asset.id,
            symbol=asset.symbol,
            name=asset.name,
            type=asset.type,
            is_active=asset.is_active,
            payout=asset.payout,
            min_order_amount=asset.min_order_amount,
            max_order_amount=asset.max_order_amount,
            min_duration=asset.min_duration,
            max_duration=asset.max_duration
        )
        for asset in assets
    ]


@router.get("/{symbol}", response_model=AssetResponse)
async def get_asset(
    symbol: str,
    db: AsyncSession = Depends(get_db)
):
    """Get asset details"""
    result = await db.execute(
        select(Asset).where(Asset.symbol == symbol)
    )
    asset = result.scalar_one_or_none()

    if not asset:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Asset not found"
        )

    return AssetResponse(
        id=asset.id,
        symbol=asset.symbol,
        name=asset.name,
        type=asset.type,
        is_active=asset.is_active,
        payout=asset.payout,
        min_order_amount=asset.min_order_amount,
        max_order_amount=asset.max_order_amount,
        min_duration=asset.min_duration,
        max_duration=asset.max_duration
    )
