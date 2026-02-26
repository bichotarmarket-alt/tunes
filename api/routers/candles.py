"""Candles router - provides historical and real-time candle data"""
from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, and_, desc
from typing import List, Optional
from datetime import datetime, timedelta
from pydantic import BaseModel
from loguru import logger

from core.database import get_db
from core.cache import get_cache
from models import Asset
from schemas import CandleResponse, CandleDataResponse
from services.data_collector.realtime import data_collector

router = APIRouter()


class TickResponse(BaseModel):
    """Response schema for current tick"""
    symbol: str
    price: float
    timestamp: float


class AvailableAssetsResponse(BaseModel):
    """Response schema for available assets"""
    assets: List[dict]


class TimeframesResponse(BaseModel):
    """Response schema for supported timeframes"""
    timeframes: List[dict]


@router.get("/history", response_model=List[CandleDataResponse])
async def get_candle_history(
    symbol: str = Query(..., description="Asset symbol (e.g., EUR/USD)"),
    timeframe: str = Query("M1", description="Timeframe: 5s, 30s, M1, M5, M15, M30, H1, H4, D1"),
    limit: int = Query(100, ge=1, le=1000, description="Number of candles to return"),
    start_time: Optional[datetime] = Query(None, description="Start time (optional)"),
    end_time: Optional[datetime] = Query(None, description="End time (optional)"),
    db: AsyncSession = Depends(get_db)
):
    """
    Get historical candle data for an asset
    
    Args:
        symbol: Asset symbol (e.g., EUR/USD)
        timeframe: Timeframe for candles
        limit: Maximum number of candles to return
        start_time: Optional start time for the range
        end_time: Optional end time for the range
    
    Returns:
        List of candle data with open, high, low, close, and timestamp
    """
    try:
        # Validate timeframe
        valid_timeframes = ['5s', '30s', 'M1', 'M5', 'M15', 'M30', 'H1', 'H4', 'D1']
        if timeframe not in valid_timeframes:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Invalid timeframe. Must be one of: {', '.join(valid_timeframes)}"
            )
        
        # Check cache first
        cache = get_cache()
        cache_key = f"candles:{symbol}:{timeframe}:{limit}:{start_time}:{end_time}"
        
        if cache:
            cached_data = await cache.get(cache_key)
            if cached_data:
                logger.debug(f"Cache hit for {symbol} {timeframe}")
                return cached_data
        
        # Convert timeframe to seconds
        timeframe_map = {
            '5s': 5,
            '30s': 30,
            'M1': 60,
            'M5': 300,
            'M15': 900,
            'M30': 1800,
            'H1': 3600,
            'H4': 14400,
            'D1': 86400
        }
        timeframe_seconds = timeframe_map[timeframe]
        
        # Get data from local storage
        candles = await data_collector.local_storage.get_candles(
            symbol=symbol,
            timeframe=timeframe_seconds,
            limit=limit,
            start_time=start_time,
            end_time=end_time
        )
        
        if not candles:
            # If no data in local storage, return empty list
            logger.warning(f"No candle data found for {symbol} {timeframe}")
            return []
        
        # Convert to response format
        response = [
            CandleDataResponse(
                timestamp=datetime.fromtimestamp(candle['timestamp']),
                open=candle['open'],
                high=candle['high'],
                low=candle['low'],
                close=candle['close'],
                volume=candle.get('volume', 0)
            )
            for candle in candles
        ]
        
        # Cache the result for 5 seconds
        if cache:
            await cache.set(cache_key, response, ttl=5)
        
        return response
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting candle history for {symbol}: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to retrieve candle history"
        )


@router.get("/tick/{symbol}", response_model=TickResponse)
async def get_current_tick(
    symbol: str,
    db: AsyncSession = Depends(get_db)
):
    """
    Get current tick price for an asset
    
    Args:
        symbol: Asset symbol (e.g., EUR/USD)
    
    Returns:
        Current price and timestamp
    """
    try:
        # Get current tick from data collector
        tick = await data_collector.local_storage.get_latest_tick(symbol)
        
        if not tick:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"No tick data available for {symbol}"
            )
        
        return TickResponse(
            symbol=symbol,
            price=tick['price'],
            timestamp=tick['timestamp']
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting tick for {symbol}: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to retrieve tick data"
        )


@router.get("/available-assets", response_model=AvailableAssetsResponse)
async def get_available_assets(
    db: AsyncSession = Depends(get_db)
):
    """
    Get list of available assets with candle data
    
    Returns:
        List of asset symbols that have historical data
    """
    try:
        # Get assets from database
        result = await db.execute(
            select(Asset).where(Asset.is_active == True)
        )
        assets = result.scalars().all()
        
        # Get assets with data from local storage
        assets_with_data = await data_collector.local_storage.get_available_assets()
        
        return AvailableAssetsResponse(
            assets=[
                {
                    "symbol": asset.symbol,
                    "name": asset.name,
                    "has_data": asset.symbol in assets_with_data
                }
                for asset in assets
            ]
        )
        
    except Exception as e:
        logger.error(f"Error getting available assets: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to retrieve available assets"
        )


@router.get("/timeframes", response_model=TimeframesResponse)
async def get_available_timeframes():
    """
    Get list of available timeframes
    
    Returns:
        List of supported timeframes
    """
    return TimeframesResponse(
        timeframes=[
            {"code": "5s", "name": "5 Seconds", "seconds": 5},
            {"code": "30s", "name": "30 Seconds", "seconds": 30},
            {"code": "M1", "name": "1 Minute", "seconds": 60},
            {"code": "M5", "name": "5 Minutes", "seconds": 300},
            {"code": "M15", "name": "15 Minutes", "seconds": 900},
            {"code": "M30", "name": "30 Minutes", "seconds": 1800},
            {"code": "H1", "name": "1 Hour", "seconds": 3600},
            {"code": "H4", "name": "4 Hours", "seconds": 14400},
            {"code": "D1", "name": "1 Day", "seconds": 86400}
        ]
    )
