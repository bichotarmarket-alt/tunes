"""Event system for the application"""
from enum import Enum
from dataclasses import dataclass
from datetime import datetime
from typing import Any, Callable, Dict, List
import threading
from loguru import logger


class EventType(Enum):
    """Event types"""
    TRADE_CREATED = "trade_created"
    TRADE_CLOSED = "trade_closed"
    BALANCE_UPDATED = "balance_updated"
    SIGNAL_GENERATED = "signal_generated"
    ACCOUNT_CONNECTED = "account_connected"
    ACCOUNT_DISCONNECTED = "account_disconnected"
    AUTOTRADE_ENABLED = "autotrade_enabled"
    AUTOTRADE_DISABLED = "autotrade_disabled"


@dataclass
class Event:
    """Event data"""
    type: EventType
    data: Dict[str, Any]
    timestamp: datetime = None
    
    def __post_init__(self):
        if self.timestamp is None:
            self.timestamp = datetime.utcnow()


class EventBus:
    """Simple event bus for pub/sub pattern"""
    
    def __init__(self):
        self._subscribers: Dict[EventType, List[Callable]] = {}
        self._lock = threading.Lock()
    
    def subscribe(self, event_type: EventType, handler: Callable):
        """Subscribe a handler to an event type"""
        with self._lock:
            if event_type not in self._subscribers:
                self._subscribers[event_type] = []
            self._subscribers[event_type].append(handler)
        logger.debug(f"Subscribed handler to event: {event_type.value}")
    
    def unsubscribe(self, event_type: EventType, handler: Callable):
        """Unsubscribe a handler from an event type"""
        with self._lock:
            if event_type in self._subscribers:
                try:
                    self._subscribers[event_type].remove(handler)
                    logger.debug(f"Unsubscribed handler from event: {event_type.value}")
                except ValueError:
                    logger.warning(f"Handler not found in event: {event_type.value}")
    
    async def publish(self, event: Event):
        """Publish an event to all subscribers"""
        with self._lock:
            handlers = list(self._subscribers.get(event.type, []))
        logger.debug(f"Publishing event: {event.type.value} to {len(handlers)} handlers")
        
        for handler in handlers:
            try:
                if hasattr(handler, '__call__'):
                    result = handler(event)
                    # Check if it's a coroutine
                    import asyncio
                    if asyncio.iscoroutine(result):
                        await result
                    else:
                        result
            except Exception as e:
                logger.error(f"Error in event handler for {event.type.value}: {e}", exc_info=True)
    
    async def publish_sync(self, event: Event):
        """Publish an event synchronously (for non-async handlers)"""
        with self._lock:
            handlers = list(self._subscribers.get(event.type, []))
        logger.debug(f"Publishing event sync: {event.type.value} to {len(handlers)} handlers")
        
        for handler in handlers:
            try:
                handler(event)
            except Exception as e:
                logger.error(f"Error in sync event handler for {event.type.value}: {e}", exc_info=True)


# Global event bus instance
event_bus = EventBus()
