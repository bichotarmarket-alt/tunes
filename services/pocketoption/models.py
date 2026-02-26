"""
Pydantic models for type safety and validation
"""

from typing import Optional
from pydantic import BaseModel, Field, validator
from datetime import datetime
from enum import Enum
import uuid


class OrderDirection(str, Enum):
    """Order direction enum"""
    CALL = "call"
    PUT = "put"


class OrderStatus(str, Enum):
    """Order status enum"""
    PENDING = "pending"
    ACTIVE = "active"
    CLOSED = "closed"
    CANCELLED = "cancelled"
    WIN = "win"
    LOSS = "loss"
    DRAW = "draw"


class ConnectionStatus(str, Enum):
    """Connection status enum"""
    CONNECTED = "connected"
    DISCONNECTED = "disconnected"
    CONNECTING = "connecting"
    RECONNECTING = "reconnecting"


class Asset(BaseModel):
    """Asset information model"""
    id: str
    name: str
    symbol: str
    is_active: bool = True
    payout: Optional[float] = None

    class Config:
        frozen = True


class Balance(BaseModel):
    """Account balance model"""
    balance: float
    currency: str = "USD"
    is_demo: bool = True
    last_updated: datetime = Field(default_factory=datetime.now)

    class Config:
        frozen = True


class Candle(BaseModel):
    """OHLC candle data model"""
    timestamp: datetime
    open: float
    high: float
    low: float
    close: float
    volume: Optional[float] = None
    asset: str
    timeframe: int  # in seconds

    @validator("high")
    def high_must_be_valid(cls, v, values):
        if "low" in values and v < values["low"]:
            raise ValueError("High must be greater than or equal to low")
        return v

    @validator("low")
    def low_must_be_valid(cls, v, values):
        if "high" in values and v > values["high"]:
            raise ValueError("Low must be less than or equal to high")
        return v

    class Config:
        frozen = True


class Order(BaseModel):
    """Order request model"""
    asset: str
    amount: float
    direction: OrderDirection
    duration: int  # in seconds
    request_id: Optional[str] = Field(default_factory=lambda: str(uuid.uuid4()))

    @validator("amount")
    def amount_must_be_positive(cls, v):
        if v <= 0:
            raise ValueError("Amount must be positive")
        return v

    @validator("duration")
    def duration_must_be_valid(cls, v):
        if v < 3:
            raise ValueError("Duration must be at least 3 seconds")
        return v


class OrderResult(BaseModel):
    """Order execution result model"""
    order_id: str
    asset: str
    amount: float
    direction: OrderDirection
    duration: int
    status: OrderStatus
    placed_at: datetime
    expires_at: datetime
    profit: Optional[float] = None
    payout: Optional[float] = None
    exit_price: Optional[float] = None
    error_message: Optional[str] = None

    class Config:
        frozen = True


class ServerTime(BaseModel):
    """Server time synchronization model"""
    server_timestamp: float
    local_timestamp: float
    offset: float
    last_sync: datetime = Field(default_factory=datetime.now)

    class Config:
        frozen = True


class ConnectionInfo(BaseModel):
    """Connection information model"""
    url: str
    region: str
    status: ConnectionStatus
    connected_at: Optional[datetime] = None
    last_ping: Optional[datetime] = None
    reconnect_attempts: int = 0

    class Config:
        frozen = True
