"""
Professional Async PocketOption API Client
"""

import asyncio
import json
import time
import uuid
from typing import Optional, List, Dict, Any, Union, Callable, Set
from datetime import datetime, timedelta
from collections import defaultdict
import pandas as pd
from loguru import logger

from sqlalchemy import select, update

from core.resilience import ResilienceExecutor, CircuitBreaker, ResiliencePresets
from .websocket import AsyncWebSocketClient
from .models import (
    Balance,
    Candle,
    Order,
    OrderResult,
    OrderStatus,
    OrderDirection,
    ServerTime,
)
from .constants import ASSETS, REGIONS, TIMEFRAMES, API_LIMITS
from .exceptions import (
    PocketOptionError,
    ConnectionError,
    AuthenticationError,
    OrderError,
    InvalidParameterError,
)


class AsyncPocketOptionClient:
    """Professional async PocketOption API client"""

    def __init__(
        self,
        ssid: str,
        is_demo: bool = True,
        region: Optional[str] = None,
        uid: int = 0,
        platform: int = 1,
        is_fast_history: bool = True,
        persistent_connection: bool = False,
        auto_reconnect: bool = True,
        enable_logging: bool = True,
        user_name: str = None,
    ):
        """
        Initialize async PocketOption client

        Args:
            ssid: Complete SSID string or raw session ID for authentication
            is_demo: Whether to use demo account
            region: Preferred region for connection
            uid: User ID (if providing raw session)
            platform: Platform identifier (1=web, 3=mobile)
            is_fast_history: Enable fast history loading
            persistent_connection: Enable persistent connection with keep-alive
            auto_reconnect: Enable automatic reconnection on disconnection
            enable_logging: Enable detailed logging (default: True)
            user_name: User name for connection identification
        """
        self.raw_ssid = ssid
        self.is_demo = is_demo
        self.preferred_region = region
        self.uid = uid
        self.platform = platform
        self.is_fast_history = is_fast_history
        self.persistent_connection = persistent_connection
        self.auto_reconnect = auto_reconnect
        self.enable_logging = enable_logging
        self.user_name = user_name or "Unknown User"

        # Configure logging based on preference
        if not enable_logging:
            logger.remove()
            logger.add(lambda msg: None, level="CRITICAL")
        
        # Validate and parse SSID
        self._original_demo = None
        self._original_php_session = None
        self._validate_and_parse_ssid(ssid)

        # Core components
        self._websocket = AsyncWebSocketClient()
        self._balance: Optional[Balance] = None
        self._orders: Dict[str, OrderResult] = {}
        self._active_orders: Dict[str, OrderResult] = {}
        self._order_results: Dict[str, OrderResult] = {}
        self._server_id_to_request_id: Dict[str, str] = {}
        self._candles_cache: Dict[str, List[Candle]] = {}
        self._server_time: Optional[ServerTime] = None
        self._event_callbacks: Dict[str, List[Callable]] = defaultdict(list)

        # Setup event handlers for websocket messages
        self._setup_event_handlers()

        # Add handler for JSON data messages
        self._websocket.add_event_handler("json_data", self._on_json_data)

        # Performance tracking
        self._operation_metrics: Dict[str, List[float]] = defaultdict(list)
        self._last_health_check = time.time()

        # Keep-alive functionality
        self._keep_alive_manager = None
        self._ping_task: Optional[asyncio.Task] = None
        self._reconnect_task: Optional[asyncio.Task] = None
        self._callback_tasks: Set[asyncio.Task] = set()
        self._is_persistent = False

        # Connection statistics
        self._connection_stats = {
            "total_connections": 0,
            "successful_connections": 0,
            "total_reconnects": 0,
            "last_ping_time": None,
            "messages_sent": 0,
            "messages_received": 0,
            "connection_start_time": None,
        }
        
        # Resilience executor para operações com timeout + retry + circuit breaker
        self._resilience = ResiliencePresets.pocket_option_client()

        logger.info(
            f"Initialized PocketOption client (demo={is_demo}, uid={self.uid}, persistent={persistent_connection})",
            extra={
                "user_name": self.user_name,
                "account_id": "",
                "account_type": "demo" if is_demo else "real"
            }
            if enable_logging else ""
        )

    def _setup_event_handlers(self):
        """Setup WebSocket event handlers"""
        self._websocket.add_event_handler("authenticated", self._on_authenticated)
        self._websocket.add_event_handler("balance_updated", self._on_balance_updated)
        self._websocket.add_event_handler("balance_data", self._on_balance_data)
        self._websocket.add_event_handler("order_opened", self._on_order_opened)
        self._websocket.add_event_handler("order_closed", self._on_order_closed)
        self._websocket.add_event_handler("update_closed_deals", self._on_update_closed_deals)
        self._websocket.add_event_handler("stream_update", self._on_stream_update)
        self._websocket.add_event_handler("candles_received", self._on_candles_received)
        self._websocket.add_event_handler("disconnected", self._on_disconnected)

    async def connect(
        self, regions: Optional[List[str]] = None, persistent: Optional[bool] = None
    ) -> bool:
        """
        Connect to PocketOption with multiple region support

        Args:
            regions: List of regions to try (uses defaults if None)
            persistent: Override persistent connection setting

        Returns:
            bool: True if connected successfully
        """
        logger.debug("Connecting to PocketOption...")
        
        # Update persistent setting if provided
        if persistent is not None:
            self.persistent_connection = bool(persistent)

        try:
            if self.persistent_connection:
                return await self._start_persistent_connection(regions)
            else:
                return await self._start_regular_connection(regions)

        except Exception as e:
            logger.error(f"Connection failed: {e}", extra={
                "user_name": self.user_name,
                "account_id": "",
                "account_type": "demo" if self.is_demo else "real"
            })
            return False

    async def _start_regular_connection(
        self, regions: Optional[List[str]] = None
    ) -> bool:
        """Start regular connection"""
        logger.info("Starting regular connection...")
        
        # Use appropriate regions based on demo mode
        if not regions:
            if self.is_demo:
                demo_urls = REGIONS.get_demo_regions()
                regions = []
                all_regions = REGIONS.get_all_regions()
                for name, url in all_regions.items():
                    if url in demo_urls:
                        regions.append(name)
                logger.info(f"Demo mode: Using demo regions: {regions}", extra={
                    "user_name": self.user_name,
                    "account_id": "",
                    "account_type": "demo"
                })
            else:
                all_regions = REGIONS.get_all_regions()
                regions = [
                    name
                    for name, url in all_regions.items()
                    if "DEMO" not in name.upper()
                ]
                logger.info(f"Live mode: Using non-demo regions: {regions}", extra={
                    "user_name": self.user_name,
                    "account_id": "",
                    "account_type": "real"
                })
        
        # Update connection stats
        self._connection_stats["total_connections"] += 1
        self._connection_stats["connection_start_time"] = time.time()

        for region in regions:
            try:
                region_url = REGIONS.get_region(region)
                if not region_url:
                    continue

                urls = [region_url]
                logger.info(f"Trying region: {region}", extra={
                    "user_name": self.user_name,
                    "account_id": "",
                    "account_type": "demo" if self.is_demo else "real"
                })

                # Try to connect
                ssid_message = self._format_session_message()
                success = await self._websocket.connect(urls, ssid_message)

                if success:
                    # Wait for authentication
                    await self._wait_for_authentication()

                    # Initialize data
                    await self._initialize_data()

                    # Start keep-alive tasks
                    await self._start_keep_alive_tasks()

                    self._connection_stats["successful_connections"] += 1
                    logger.info("Successfully connected and authenticated", extra={
                        "user_name": self.user_name,
                        "account_id": "",
                        "account_type": "demo" if self.is_demo else "real"
                    })
                    return True

            except Exception as e:
                logger.warning(f"Failed to connect to region {region}: {e}", extra={
                    "user_name": self.user_name,
                    "account_id": "",
                    "account_type": "demo" if self.is_demo else "real"
                })
                continue

        return False

    async def _start_persistent_connection(
        self, regions: Optional[List[str]] = None
    ) -> bool:
        """Start persistent connection with automatic keep-alive"""
        logger.debug("Starting persistent connection with automatic keep-alive...")

        # Import the keep-alive manager
        from .keep_alive import ConnectionKeepAlive

        # Create keep-alive manager
        complete_ssid = self.raw_ssid
        self._keep_alive_manager = ConnectionKeepAlive(complete_ssid, self.is_demo, user_name=getattr(self, 'user_name', None))

        # Add event handlers
        self._keep_alive_manager.add_event_handler(
            "connected", self._on_keep_alive_connected
        )
        self._keep_alive_manager.add_event_handler(
            "reconnected", self._on_keep_alive_reconnected
        )
        self._keep_alive_manager.add_event_handler(
            "message_received", self._on_keep_alive_message
        )

        # Add handlers for forwarded WebSocket events
        self._keep_alive_manager.add_event_handler(
            "balance_data", self._on_balance_data
        )
        self._keep_alive_manager.add_event_handler(
            "balance_updated", self._on_balance_updated
        )
        self._keep_alive_manager.add_event_handler(
            "authenticated", self._on_authenticated
        )
        self._keep_alive_manager.add_event_handler(
            "order_opened", self._on_order_opened
        )
        self._keep_alive_manager.add_event_handler(
            "order_closed", self._on_order_closed
        )
        self._keep_alive_manager.add_event_handler(
            "stream_update", self._on_stream_update
        )
        self._keep_alive_manager.add_event_handler(
            "candles_received", self._on_candles_received
        )
        self._keep_alive_manager.add_event_handler("json_data", self._on_json_data)

        # Connect with keep-alive
        success = await self._keep_alive_manager.connect_with_keep_alive(regions)

        if success:
            self._is_persistent = True
            return True
        else:
            logger.error("Failed to establish persistent connection", extra={
                "user_name": self.user_name,
                "account_id": "",
                "account_type": "demo" if self.is_demo else "real"
            })
            return False

    async def _start_keep_alive_tasks(self):
        """Start keep-alive tasks for regular connection"""
        logger.info("Starting keep-alive tasks...")

        # Start ping task
        self._ping_task = asyncio.create_task(self._ping_loop())

        # Start reconnection monitor if auto_reconnect is enabled
        if self.auto_reconnect:
            self._reconnect_task = asyncio.create_task(self._reconnection_monitor())

    async def _ping_loop(self):
        """Ping loop for regular connections"""
        while self.is_connected and not self._is_persistent:
            try:
                await self._websocket.send_message('42["ps"]')
                self._connection_stats["last_ping_time"] = time.time()
                await asyncio.sleep(20)
            except Exception as e:
                logger.warning(f"Ping failed: {e}", extra={
                    "user_name": self.user_name,
                    "account_id": "",
                    "account_type": "demo" if self.is_demo else "real"
                })
                break

    async def _reconnection_monitor(self):
        """Monitor and handle reconnections for regular connections"""
        while self.auto_reconnect and not self._is_persistent:
            await asyncio.sleep(30)

            if not self.is_connected:
                logger.info("Connection lost, attempting reconnection...", extra={
                    "user_name": self.user_name,
                    "account_id": "",
                    "account_type": "demo" if self.is_demo else "real"
                })
                self._connection_stats["total_reconnects"] += 1

                try:
                    success = await self._start_regular_connection()
                    if success:
                        logger.info("Reconnection successful", extra={
                            "user_name": self.user_name,
                            "account_id": "",
                            "account_type": "demo" if self.is_demo else "real"
                        })
                    else:
                        logger.error("Reconnection failed", extra={
                            "user_name": self.user_name,
                            "account_id": "",
                            "account_type": "demo" if self.is_demo else "real"
                        })
                        await asyncio.sleep(10)
                except Exception as e:
                    logger.error(f"Reconnection error: {e}", extra={
                        "user_name": self.user_name,
                        "account_id": "",
                        "account_type": "demo" if self.is_demo else "real"
                    })
                    await asyncio.sleep(10)

    async def disconnect(self) -> None:
        """Disconnect from PocketOption and cleanup"""
        logger.info("Disconnecting from PocketOption...", extra={
            "user_name": self.user_name,
            "account_id": "",
            "account_type": "demo" if self.is_demo else "real"
        })

        # Cancel tasks
        tasks_to_cancel = []
        if self._ping_task and not self._ping_task.done():
            tasks_to_cancel.append(self._ping_task)
        if self._reconnect_task and not self._reconnect_task.done():
            tasks_to_cancel.append(self._reconnect_task)
        
        # Cancel callback tasks
        for task in self._callback_tasks:
            if not task.done():
                tasks_to_cancel.append(task)
        self._callback_tasks.clear()

        # Cancel all tasks with timeout to avoid RecursionError
        if tasks_to_cancel:
            for task in tasks_to_cancel:
                task.cancel()
            try:
                # Use shield to prevent cancellation of the wait operation itself
                async def wait_for_tasks():
                    for task in tasks_to_cancel:
                        if not task.done():
                            try:
                                await asyncio.wait_for(asyncio.shield(task), timeout=0.1)
                            except (asyncio.CancelledError, asyncio.TimeoutError):
                                pass
                            except Exception:
                                pass

                await asyncio.wait_for(wait_for_tasks(), timeout=2.0)
            except asyncio.TimeoutError:
                logger.debug("Timeout ao aguardar finalização das tasks canceladas")
            except Exception as e:
                logger.debug(f"Erro ao aguardar finalização das tasks: {e}")

        # Disconnect based on connection type
        if self._is_persistent and self._keep_alive_manager:
            await self._keep_alive_manager.disconnect()
        else:
            await self._websocket.disconnect()

        # Reset state
        self._is_persistent = False
        self._balance = None
        self._orders.clear()

    async def get_balance(self) -> Balance:
        """
        Get current account balance (com timeout e retry protegidos)

        Returns:
            Balance: Current balance information
        """
        if not self.is_connected:
            raise ConnectionError("Not connected to PocketOption")

        # Usar ResilienceExecutor para proteção contra timeout
        async def _fetch_balance():
            # Request balance update if needed
            if (
                not self._balance
                or (datetime.now() - self._balance.last_updated).seconds > 60
            ):
                await self._request_balance_update()
                await asyncio.sleep(0.5)  # Reduzido de 1s para 0.5s com timeout protegido

            if not self._balance:
                raise PocketOptionError("Balance data not available")
            
            return self._balance

        return await self._resilience.execute(
            _fetch_balance(),
            operation_name="get_balance"
        )

    async def place_order(
        self, asset: str, amount: float, direction: OrderDirection, duration: int
    ) -> OrderResult:
        """
        Place a binary options order (com timeout protegido e retry limitado)

        Args:
            asset: Asset symbol (e.g., "EURUSD_otc")
            amount: Order amount
            direction: OrderDirection.CALL or OrderDirection.PUT
            duration: Duration in seconds

        Returns:
            OrderResult: Order placement result
        """
        if not self.is_connected:
            raise ConnectionError("Not connected to PocketOption")
        
        # Validate parameters
        self._validate_order_parameters(asset, amount, direction, duration)

        async def _execute_place_order():
            # Create order
            order_id = str(uuid.uuid4())
            order = Order(
                asset=asset,
                amount=amount,
                direction=direction,
                duration=duration,
                request_id=order_id,
            )
            
            # Send order
            await self._send_order(order)

            # Wait for result
            result = await self._wait_for_order_result(order_id, order)

            logger.info(f"Order placed: {result.order_id} - {result.status}")
            return result

        # Usar executor específico para trades (timeout maior, menos retries)
        trade_executor = ResilienceExecutor(
            timeout=15.0,
            retries=1,  # Apenas 1 retry para evitar duplicação de ordens
            backoff_base=1.0,
            circuit_breaker=self._resilience.circuit_breaker,  # Compartilha circuit breaker
            name="trade_executor",
            retry_exceptions=[asyncio.TimeoutError]  # Só retry em timeout, não em erros de negócio
        )

        try:
            return await trade_executor.execute(
                _execute_place_order(),
                operation_name="place_order"
            )
        except Exception as e:
            logger.error(f"Order placement failed: {e}")
            raise OrderError(f"Failed to place order: {e}")

    async def get_candles(
        self,
        asset: str,
        timeframe: Union[str, int],
        count: int = 100,
        end_time: Optional[datetime] = None,
    ) -> List[Candle]:
        """
        Get historical candle data

        Args:
            asset: Asset symbol
            timeframe: Timeframe (e.g., "1m", "5m", 60)
            count: Number of candles to retrieve
            end_time: End time for data (defaults to now)

        Returns:
            List[Candle]: Historical candle data
        """
        logger.info(f" get_candles called for asset={asset}, timeframe={timeframe}, count={count}")
        
        # Check connection and attempt reconnection if needed
        if not self.is_connected:
            if self.auto_reconnect:
                logger.info("Connection lost, attempting reconnection...")
                reconnected = await self._attempt_reconnection()
                if not reconnected:
                    raise ConnectionError("Not connected and reconnection failed")
            else:
                raise ConnectionError("Not connected to PocketOption")

        # Convert timeframe to seconds
        if isinstance(timeframe, str):
            timeframe_seconds = TIMEFRAMES.get(timeframe, 60)
        else:
            timeframe_seconds = timeframe

        # Validate asset
        if asset not in ASSETS:
            raise InvalidParameterError(f"Invalid asset: {asset}")

        # Set default end time
        if not end_time:
            end_time = datetime.now()

        max_retries = 2
        for attempt in range(max_retries):
            try:
                # Request candle data
                candles = await self._request_candles(
                    asset, timeframe_seconds, count, end_time
                )

                # Cache results
                cache_key = f"{asset}_{timeframe_seconds}"
                self._candles_cache[cache_key] = candles

                logger.info(f"Retrieved {len(candles)} candles for {asset}")
                return candles

            except Exception as e:
                if "WebSocket is not connected" in str(e) and attempt < max_retries - 1:
                    logger.warning(
                        f"Connection lost during candle request for {asset}, attempting reconnection..."
                    )
                    if self.auto_reconnect:
                        reconnected = await self._attempt_reconnection()
                        if reconnected:
                            logger.info(
                                f" Reconnected, retrying candle request for {asset}"
                            )
                            continue

                logger.error(f"Failed to get candles for {asset}: {e}")
                raise PocketOptionError(f"Failed to get candles: {e}")

        raise PocketOptionError(f"Failed to get candles after {max_retries} attempts")

    async def check_order_result(self, order_id: str) -> Optional[OrderResult]:
        """
        Check the result of a specific order

        Args:
            order_id: Order ID to check

        Returns:
            OrderResult: Order result or None if not found
        """
        # First check completed orders
        if order_id in self._order_results:
            return self._order_results[order_id]

        # Then check active orders
        if order_id in self._active_orders:
            return self._active_orders[order_id]

        return None

    async def get_active_orders(self) -> List[OrderResult]:
        """
        Get all active orders

        Returns:
            List[OrderResult]: Active orders
        """
        return list(self._active_orders.values())

    def add_event_callback(self, event: str, callback: Callable) -> None:
        """
        Add event callback

        Args:
            event: Event name (e.g., 'order_closed', 'balance_updated')
            callback: Callback function
        """
        if event not in self._event_callbacks:
            self._event_callbacks[event] = []
        self._event_callbacks[event].append(callback)

    def remove_event_callback(self, event: str, callback: Callable) -> None:
        """
        Remove event callback

        Args:
            event: Event name
            callback: Callback function to remove
        """
        if event in self._event_callbacks:
            try:
                self._event_callbacks[event].remove(callback)
            except ValueError:
                pass

    @property
    def is_connected(self) -> bool:
        """Check if client is connected (including persistent connections)"""
        if self._is_persistent and self._keep_alive_manager:
            return self._keep_alive_manager.is_connected
        else:
            return self._websocket.is_connected

    @property
    def connection_info(self):
        """Get connection information (including persistent connections)"""
        if self._is_persistent and self._keep_alive_manager:
            return self._keep_alive_manager.connection_info
        else:
            return self._websocket.connection_info

    async def send_message(self, message: str) -> bool:
        """Send message through active connection (com timeout protegido)"""
        async def _send():
            if self._is_persistent and self._keep_alive_manager:
                return await self._keep_alive_manager.send_message(message)
            else:
                await self._resilience.execute(
                    self._websocket.send_message(message),
                    operation_name="send_message"
                )
                return True
        
        try:
            return await _send()
        except Exception as e:
            logger.error(f"Failed to send message: {e}")
            return False

    def get_connection_stats(self) -> Dict[str, Any]:
        """Get comprehensive connection statistics"""
        stats = self._connection_stats.copy()

        if self._is_persistent and self._keep_alive_manager:
            stats.update(self._keep_alive_manager.get_stats())
        else:
            stats.update({
                "websocket_connected": self._websocket.is_connected,
                "connection_info": self._websocket.connection_info,
            })

        return stats

    # Private methods

    def _validate_and_parse_ssid(self, ssid: str) -> None:
        """Validate and parse SSID format"""
        if not ssid or not isinstance(ssid, str):
            raise InvalidParameterError(
                "SSID must be a non-empty string. "
                "Expected format: 42[\"auth\",{\"session\":\"...\",\"isDemo\":1,\"uid\":0,\"platform\":1}]"
            )
        
        ssid = ssid.strip()
        
        # Check if it's a complete SSID format
        if ssid.startswith('42["auth",'):
            self._parse_complete_ssid(ssid)
            # Validate session ID
            if not self.session_id or len(self.session_id) < 10:
                raise InvalidParameterError(
                    f"Invalid SSID format - session ID is too short or missing. "
                    f"Please ensure your SSID is in the correct format."
                )
        else:
            # Treat as raw session ID
            if len(ssid) < 10:
                logger.warning(
                    f"Raw session ID appears to be too short ({len(ssid)} chars). "
                    f"If you're having connection issues, please use the complete SSID format."
                )
            self.session_id = ssid
            self._complete_ssid = None

    def _format_session_message(self) -> str:
        """Format session authentication message"""
        # Use original PHP serialized session if available
        if self._original_php_session:
            auth_data = {
                "session": self._original_php_session,
                "isDemo": 1 if self.is_demo else 0,
                "uid": self.uid,
                "platform": self.platform,
            }
        else:
            auth_data = {
                "session": self.session_id,
                "isDemo": 1 if self.is_demo else 0,
                "uid": self.uid,
                "platform": self.platform,
            }

        if self.is_fast_history:
            auth_data["isFastHistory"] = True
            auth_data["isOptimized"] = True

        return f'42["auth",{json.dumps(auth_data)}]'

    def _parse_complete_ssid(self, ssid: str) -> None:
        """Parse complete SSID auth message to extract components"""
        try:
            # Extract JSON part
            json_start = ssid.find("{")
            json_end = ssid.rfind("}") + 1
            if json_start != -1 and json_end > json_start:
                json_part = ssid[json_start:json_end]
                data = json.loads(json_part)

                session_value = data.get("session", "")
                if not session_value:
                    raise InvalidParameterError(
                        "SSID is missing the 'session' field."
                    )
                
                # Check if session contains PHP serialized data
                if session_value.startswith("a:4:"):
                    # Store the complete PHP serialized session
                    self._original_php_session = session_value
                    # Extract session_id from PHP data for logging/debugging
                    import re
                    match = re.search(r's:32:"([a-f0-9]{32})"', session_value)
                    if match:
                        self.session_id = match.group(1)
                    else:
                        self.session_id = session_value
                else:
                    # Use the session value directly
                    self.session_id = session_value
                    self._original_php_session = None
                
                # Store original demo value
                self._original_demo = bool(data.get("isDemo", 1))
                self.uid = data.get("uid", 0)
                self.platform = data.get("platform", 1)
                self._complete_ssid = None
            else:
                raise InvalidParameterError(
                    "Could not parse SSID - JSON object not found."
                )
        except json.JSONDecodeError as e:
            raise InvalidParameterError(
                f"Invalid SSID format - JSON parsing failed: {e}."
            )
        except InvalidParameterError:
            raise
        except Exception as e:
            raise InvalidParameterError(
                f"Failed to parse SSID: {e}."
            )

    async def _wait_for_authentication(self, timeout: float = 10.0) -> None:
        """Wait for authentication to complete"""
        auth_received = False
        auth_error = None

        def on_auth(data):
            nonlocal auth_received
            auth_received = True
        
        def on_auth_error(data):
            nonlocal auth_error
            auth_error = data.get("message", "Unknown authentication error")

        # Add temporary handlers
        self._websocket.add_event_handler("authenticated", on_auth)
        self._websocket.add_event_handler("auth_error", on_auth_error)

        try:
            # Wait for authentication
            start_time = time.time()
            while not auth_received and not auth_error and (time.time() - start_time) < timeout:
                await asyncio.sleep(0.1)

            if auth_error:
                raise AuthenticationError(
                    f"Authentication failed: {auth_error}. "
                    f"Please verify your SSID is correct."
                )
            
            if not auth_received:
                raise AuthenticationError(
                    "Authentication timeout - server did not respond. "
                    "Please get a fresh SSID from browser DevTools."
                )

        finally:
            # Remove temporary handlers
            self._websocket.remove_event_handler("authenticated", on_auth)
            self._websocket.remove_event_handler("auth_error", on_auth_error)

    async def _initialize_data(self) -> None:
        """Initialize client data after connection"""
        # Request initial balance
        await self._request_balance_update()

        # Setup time synchronization
        await self._setup_time_sync()

    async def _request_balance_update(self) -> None:
        """Request balance update from server"""
        message = '42["getBalance"]'

        if self._is_persistent and self._keep_alive_manager:
            await self._keep_alive_manager.send_message(message)
        else:
            await self._websocket.send_message(message)

    async def _setup_time_sync(self) -> None:
        """Setup server time synchronization"""
        local_time = datetime.now().timestamp()
        self._server_time = ServerTime(
            server_timestamp=local_time, local_timestamp=local_time, offset=0.0
        )

    def _validate_order_parameters(
        self, asset: str, amount: float, direction: OrderDirection, duration: int
    ) -> None:
        """Validate order parameters"""
        if asset not in ASSETS:
            raise InvalidParameterError(f"Invalid asset: {asset}")

        if (
            amount < API_LIMITS["min_order_amount"]
            or amount > API_LIMITS["max_order_amount"]
        ):
            raise InvalidParameterError(
                f"Amount must be between {API_LIMITS['min_order_amount']} and {API_LIMITS['max_order_amount']}"
            )

        if (
            duration < API_LIMITS["min_duration"]
            or duration > API_LIMITS["max_duration"]
        ):
            raise InvalidParameterError(
                f"Duration must be between {API_LIMITS['min_duration']} and {API_LIMITS['max_duration']} seconds"
            )

    async def _send_order(self, order: Order) -> None:
        """Send order to server"""
        asset_name = order.asset

        # Create the message in the correct PocketOption format
        # Usar "openOrder" em vez de "buy", "action" em vez de "direction", "time" em vez de "exp"
        message = f'42["openOrder",{{"asset":"{asset_name}","amount":{order.amount},"action":"{order.direction.value}","isDemo":{1 if self.is_demo else 0},"requestId":"{order.request_id}","optionType":100,"time":{order.duration}}}]'

        if self._is_persistent and self._keep_alive_manager:
            await self._keep_alive_manager.send_message(message)
        else:
            await self._websocket.send_message(message)

    async def _wait_for_order_result(self, order_id: str, order: Order) -> OrderResult:
        """Wait for order result"""
        # Wait for order to be processed
        max_wait = 10.0
        start_time = time.time()

        while time.time() - start_time < max_wait:
            result = await self.check_order_result(order_id)
            if result and result.status != OrderStatus.PENDING:
                return result
            await asyncio.sleep(0.1)

        # Create fallback result if no response
        return OrderResult(
            order_id=order_id,
            asset=order.asset,
            amount=order.amount,
            direction=order.direction,
            duration=order.duration,
            status=OrderStatus.PENDING,
            placed_at=datetime.now(),
            expires_at=datetime.now() + timedelta(seconds=order.duration),
        )

    async def _request_candles(
            self, asset: str, timeframe: int, count: int, end_time: datetime
        ) -> List[Candle]:
        """Request candle data from server using changeSymbol"""

        # Use changeSymbol with asset name (not asset_id)
        data = {
            "asset": str(asset),
            "period": timeframe
        }
        message_data = ["changeSymbol", data]
        message = f'42{json.dumps(message_data)}'

        # Create a future to wait for the response
        candle_future = asyncio.Future()
        request_id = f"{asset}_{timeframe}"

        # Store the future for this request
        if not hasattr(self, "_candle_requests"):
            self._candle_requests = {}
        self._candle_requests[request_id] = candle_future

        # Send the request using appropriate connection
        if self._is_persistent and self._keep_alive_manager:
            await self._keep_alive_manager.send_message(message)
        else:
            await self._websocket.send_message(message)

        try:
            # Wait for the response (with timeout)
            candles = await asyncio.wait_for(candle_future, timeout=10.0)
            return candles
        except asyncio.TimeoutError:
            logger.warning(f"Candle request timed out for {asset}")
            return []
        finally:
            # Clean up the request
            if request_id in self._candle_requests:
                del self._candle_requests[request_id]

    async def _attempt_reconnection(self) -> bool:
        """Attempt to reconnect"""
        logger.info("Attempting reconnection...")
        return await self._start_regular_connection()

    # Event handlers

    async def _on_authenticated(self, data: Dict[str, Any]):
        """Handle authentication success"""
        logger.info("Authentication successful")
        await self._emit_event("authenticated", data)
        
        # Verificar trades ativos ao conectar para corrigir dados incompletos
        try:
            from core.database import get_db_context
            from models import Trade, TradeStatus
            from sqlalchemy import select
            
            async with get_db_context() as db:
                # Buscar trades ativos que expiraram E trades CLOSED sem resultado
                five_minutes_ago = datetime.utcnow() - pd.Timedelta(minutes=5)
                from sqlalchemy import or_, and_
                result = await db.execute(
                    select(Trade).where(
                        or_(
                            and_(
                                Trade.status == TradeStatus.ACTIVE,
                                Trade.expires_at <= five_minutes_ago
                            ),
                            and_(
                                Trade.status == TradeStatus.CLOSED,
                                Trade.profit.is_(None),
                                Trade.payout.is_(None),
                                Trade.expires_at <= five_minutes_ago
                            )
                        )
                    )
                )
                expired_trades = result.scalars().all()
                
                if expired_trades:
                    logger.info(f"📊 Verificando {len(expired_trades)} trades expirados/incompletos ao conectar...")
                    
                    for trade in expired_trades:
                        # Verificar resultado usando o order_id
                        order_id_to_check = trade.order_id if trade.order_id else trade.id
                        order_result = await self.check_order_result(order_id_to_check)
                        
                        if order_result and order_result.status in [OrderStatus.WIN, OrderStatus.LOSS]:
                            # Atualizar trade
                            trade.status = TradeStatus.WIN if order_result.status == OrderStatus.WIN else TradeStatus.LOSS
                            trade.profit = order_result.profit
                            trade.payout = order_result.payout
                            trade.closed_at = datetime.utcnow()
                            
                            logger.success(f"[SUCCESS] Trade {trade.id[:8]}... atualizado: {trade.status} (lucro: ${trade.profit if trade.profit else 0:.2f})")
                        elif order_result and order_result.status == OrderStatus.CANCELLED:
                            # Trade cancelado
                            trade.status = TradeStatus.CANCELLED
                            trade.closed_at = datetime.utcnow()
                            
                            logger.warning(f"[WARNING] Trade {trade.id[:8]}... cancelado")
                        else:
                            # Trade ainda não tem resultado, marcar como CLOSED
                            trade.status = TradeStatus.CLOSED
                            trade.closed_at = datetime.utcnow()
                            trade.exit_price = trade.entry_price if trade.entry_price else 0
                            trade.profit = 0
                            trade.payout = 0
                            
                            logger.warning(f"[WARNING] Trade {trade.id[:8]}... fechado sem resultado definido")
                    
                    await db.commit()
                    logger.success(f"[TARGET] {len(expired_trades)} trades atualizados ao conectar")
        except Exception as e:
            logger.error(f"Erro ao verificar trades ao conectar: {e}", exc_info=True)

    async def _on_balance_updated(self, data: Dict[str, Any]):
        """Handle balance update"""
        if "balance" in data:
            self._balance = Balance(
                balance=data["balance"],
                currency="USD",
                is_demo=data.get("isDemo", True),
                last_updated=datetime.now()
            )
            logger.info(f"Balance updated: {self._balance.balance}")
            # Emit event to external callbacks
            await self._emit_event("balance_updated", data)

    async def _on_balance_data(self, data: Dict[str, Any]):
        """Handle balance data (bytes message)"""
        if "balance" in data:
            self._balance = Balance(
                balance=data["balance"],
                currency="USD",
                is_demo=data.get("isDemo", True),
                last_updated=datetime.now()
            )
            # Emit event to external callbacks
            await self._emit_event("balance_data", data)

    async def _on_order_opened(self, data: Dict[str, Any]):
        """Handle order opened"""
        logger.info(f"Order opened: {data}")
        
        # Extrair order_id dos dados
        order_id = data.get('id') or data.get('order_id') or data.get('request_id')
        if not order_id:
            logger.warning(f"Order opened event without order_id: {data}")
            return
        
        # Criar OrderResult e adicionar a active_orders
        order_result = OrderResult(
            order_id=order_id,
            asset=data.get('asset', ''),
            amount=data.get('amount', 0),
            direction=OrderDirection.CALL if data.get('direction') == 'call' else OrderDirection.PUT,
            duration=data.get('duration', 0),
            status=OrderStatus.PENDING,
            placed_at=datetime.now(),
            expires_at=datetime.now() + timedelta(seconds=data.get('duration', 0))
        )
        
        self._active_orders[order_id] = order_result
        logger.info(f"Order {order_id[:8]}... added to active_orders")

    async def _on_order_closed(self, data: Dict[str, Any]):
        """Handle order closed"""
        logger.info(f"Order closed: {data}")
        
        # Extrair order_id dos dados
        order_id = data.get('id') or data.get('order_id') or data.get('request_id')
        if not order_id:
            logger.warning(f"Order closed event without order_id: {data}")
            return
        
        # Mover de active_orders para order_results
        if order_id in self._active_orders:
            order_result = self._active_orders.pop(order_id)

            # Atualizar status baseado nos dados recebidos
            if 'win' in data and data['win']:
                order_result.status = OrderStatus.WIN
                profit = data.get('profit', 0)
                # Validar profit para vitórias
                if profit is None or profit <= 0:
                    logger.warning(f"[WARNING] Profit inválido para vitória: {profit}, usando 0")
                    profit = 0
                order_result.profit = profit
                order_result.payout = data.get('payout', 0)
            elif 'lose' in data and data['lose']:
                order_result.status = OrderStatus.LOSS
                profit = data.get('profit', 0)
                # Para perdas, profit deve ser negativo ou 0
                if profit is None:
                    profit = 0
                elif profit > 0:
                    logger.warning(f"[WARNING] Profit positivo para perda: {profit}, deve ser negativo ou 0")
                    profit = -profit  # Inverter sinal se estiver positivo
                order_result.profit = profit
                order_result.payout = data.get('payout', 0)
            elif 'draw' in data and data['draw']:
                order_result.status = OrderStatus.DRAW
                order_result.profit = 0
                order_result.payout = 0
            else:
                # Verificar se é empate baseado no profit
                profit = data.get('profit', 0)
                if profit == 0:
                    order_result.status = OrderStatus.DRAW
                    order_result.profit = 0
                    order_result.payout = 0
                else:
                    order_result.status = OrderStatus.CLOSED
            
            # Armazenar em order_results
            self._order_results[order_id] = order_result
            logger.info(f"Order {order_id[:8]}... moved to results with status {order_result.status}")
        else:
            logger.warning(f"Order {order_id[:8]}... not found in active_orders")

    async def _on_stream_update(self, data: Dict[str, Any]):
        """Handle stream update"""
        pass

    async def _on_candles_received(self, data: Dict[str, Any]):
        """Handle candles received"""
        await self._emit_event("candles_received", data)

    async def _on_disconnected(self, data: Dict[str, Any]):
        """Handle disconnection"""
        logger.warning("Disconnected from PocketOption")

    async def _on_update_closed_deals(self, data: List[Dict[str, Any]]):
        """Handle updateClosedDeals event - corrige trades incompletos no banco de dados"""
        if not data or not isinstance(data, list):
            logger.debug("updateClosedDeals: dados vazios ou inválidos")
            return

        logger.info(f"📊 Recebido evento updateClosedDeals com {len(data)} operações fechadas")

        try:
            from core.database import get_db_context
            from models import Trade, TradeStatus

            async with get_db_context() as db:
                updated_count = 0

                for deal in data:
                    if not isinstance(deal, dict):
                        continue

                    deal_id = deal.get('id')
                    if not deal_id:
                        continue

                    profit = deal.get('profit')
                    close_price = deal.get('closePrice')
                    close_time = deal.get('closeTime')

                    # Buscar trades no banco de dados que correspondem a este deal
                    # Busca por order_id ou por critérios de matching (asset, amount, close time)
                    # Inclui trades ACTIVE e trades CLOSED sem resultado (profit=None ou 0)
                    from sqlalchemy import or_, and_
                    query = select(Trade).where(
                        or_(
                            Trade.status == TradeStatus.ACTIVE,
                            and_(
                                Trade.status == TradeStatus.CLOSED,
                                or_(
                                    Trade.profit.is_(None),
                                    Trade.profit == 0
                                ),
                                Trade.payout.is_(None)
                            )
                        ) &
                        ((Trade.order_id == deal_id) | (
                            (Trade.profit.is_(None)) &
                            (Trade.amount == deal.get('amount')) &
                            (Trade.exit_price.is_(None))
                        ))
                    )

                    result = await db.execute(query)
                    trades = result.scalars().all()

                    for trade in trades:
                        # Verificar se este trade precisa ser atualizado
                        needs_update = False

                        if trade.profit is None and profit is not None:
                            needs_update = True
                            # Determinar status baseado no profit
                            if profit is not None and profit > 0:
                                trade.status = TradeStatus.WIN
                            elif profit is not None and profit < 0:
                                trade.status = TradeStatus.LOSE
                            elif profit is not None and profit == 0:
                                trade.status = TradeStatus.DRAW

                        if trade.exit_price is None and close_price is not None:
                            needs_update = True
                            trade.exit_price = close_price

                        if needs_update:
                            trade.profit = profit
                            trade.payout = deal.get('payout')
                            trade.order_id = deal_id  # Garantir que o order_id esteja definido

                            # Tentar converter closeTime para datetime
                            if close_time:
                                try:
                                    if isinstance(close_time, str):
                                        trade.closed_at = datetime.strptime(close_time, "%Y-%m-%d %H:%M:%S")
                                    elif isinstance(close_time, (int, float)):
                                        trade.closed_at = datetime.fromtimestamp(close_time)
                                except Exception as e:
                                    logger.warning(f"Erro ao converter closeTime: {e}")

                            updated_count += 1
                            logger.info(
                                f"[SUCCESS] Trade {trade.id[:8]}... atualizado: "
                                f"status={trade.status}, profit=${profit}, "
                                f"close_price={close_price}"
                            )

                if updated_count > 0:
                    await db.commit()
                    logger.success(f"[TARGET] {updated_count} trades incompletos corrigidos no banco de dados")
                else:
                    logger.debug("Nenhum trade incompleto encontrado para atualizar")

        except Exception as e:
            logger.error(f"Erro ao processar updateClosedDeals: {e}")
            import traceback
            traceback.print_exc()

    async def _on_json_data(self, data: Dict[str, Any]) -> None:
        """Handle JSON data message"""
        # Check if this is candles data response (like legacy code does)
        if isinstance(data, dict) and "candles" in data and isinstance(data["candles"], list):
            # Find the corresponding candle request
            if hasattr(self, "_candle_requests"):
                # Try to match the request based on asset and period
                asset = data.get("asset")
                period = data.get("period")
                if asset and period:
                    request_id = f"{asset}_{period}"
                    if (
                        request_id in self._candle_requests
                        and not self._candle_requests[request_id].done()
                    ):
                        candles = self._parse_candles_data(data["candles"], asset, period)
                        self._candle_requests[request_id].set_result(candles)
                        return

        # Check if this is detailed order data with requestId (like legacy code does)
        if "requestId" in data and "asset" in data and "amount" in data:
            request_id = str(data["requestId"])

            # Store mapping from server ID to request ID if server ID is present and valid
            if "id" in data and data["id"]:
                server_id = str(data["id"])
                if server_id:  # Ensure string is not empty
                    self._server_id_to_request_id[server_id] = request_id
                    logger.debug(f"Mapped server ID {server_id} to request ID {request_id}")

            # If this is a new order, add it to tracking
            if (
                request_id not in self._active_orders
                and request_id not in self._order_results
            ):
                order_result = OrderResult(
                    order_id=request_id,
                    asset=data.get("asset", "UNKNOWN"),
                    amount=float(data.get("amount", 0)) if isinstance(data.get("amount"), (int, float)) else 0.0,
                    direction=OrderDirection.CALL
                    if data.get("command", 0) == 0
                    else OrderDirection.PUT,
                    duration=int(data.get("time", 60)),
                    status=OrderStatus.ACTIVE,
                    placed_at=datetime.now(),
                    expires_at=datetime.now()
                    + timedelta(seconds=int(data.get("time", 60))),
                    profit=float(data.get("profit", 0)) if isinstance(data.get("profit"), (int, float)) else None,
                    payout=data.get("payout"),
                )

                # Add to active orders
                self._active_orders[request_id] = order_result
                logger.success(f"Order {request_id[:8]}... added to tracking from JSON data")

                await self._emit_event("order_opened", data)

        # Check if this is order result data with deals (like legacy code does)
        elif "deals" in data and isinstance(data["deals"], list):
            for deal in data["deals"]:
                if isinstance(deal, dict) and "id" in deal:
                    server_deal_id = str(deal["id"])
                    
                    # Try to find the request_id for this server deal ID
                    request_id = self._server_id_to_request_id.get(server_deal_id)
                    
                    # If we have a mapping, use request_id to find the order
                    # Otherwise, fall back to trying server_deal_id directly
                    lookup_id = request_id or server_deal_id
                    
                    if lookup_id in self._active_orders:
                        active_order = self._active_orders[lookup_id]
                        profit = float(deal.get("profit", 0)) if isinstance(deal.get("profit"), (int, float)) else 0.0

                        # Determine status
                        if profit > 0:
                            status = OrderStatus.WIN
                        elif profit < 0:
                            status = OrderStatus.LOSS
                        else:
                            status = OrderStatus.LOSS  # Default for zero profit

                        result = OrderResult(
                            order_id=active_order.order_id,
                            asset=active_order.asset,
                            amount=active_order.amount,
                            direction=active_order.direction,
                            duration=active_order.duration,
                            status=status,
                            placed_at=active_order.placed_at,
                            expires_at=active_order.expires_at,
                            profit=profit,
                            payout=deal.get("payout"),
                            exit_price=deal.get("closePrice"),
                        )

                        # Move from active to completed - use the original order_id (request_id)
                        self._order_results[active_order.order_id] = result
                        del self._active_orders[lookup_id]
                        
                        # Clean up the server ID mapping
                        if request_id and server_deal_id in self._server_id_to_request_id:
                            del self._server_id_to_request_id[server_deal_id]

                        logger.success(
                            f"Order {active_order.order_id[:8]}... completed via JSON data: {status.value} - Profit: ${profit:.2f}"
                        )
                        await self._emit_event("order_closed", result)

        # Emit event to registered callbacks
        await self._emit_event("json_data", data)

    async def _on_stream_update(self, data: Dict[str, Any]) -> None:
        """Handle stream update event - includes real-time candle data"""
        # Check if this is candle data from changeSymbol subscription
        # The format from updateStream is: {"asset":"EURUSD_otc","period":60,"data":[...]}
        if isinstance(data, dict):
            asset = data.get("asset")
            period = data.get("period")
            candles_data = data.get("data") or data.get("candles")
            
            if asset and period and candles_data:
                await self._handle_candles_stream(data)
        else:
            pass

        # Emit event to registered callbacks
        await self._emit_event("stream_update", data)

    def _parse_candles_data(self, candles_data: List[Any], asset: str, timeframe: int):
        """Parse candles data from server response"""
        candles = []

        try:
            if isinstance(candles_data, list):
                for candle_data in candles_data:
                    if isinstance(candle_data, (list, tuple)) and len(candle_data) >= 6:
                        # Server format: [timestamp, open, close, high, low, volume]
                        candle = Candle(
                            timestamp=datetime.fromtimestamp(candle_data[0]) if candle_data[0] else datetime.now(),
                            open=float(candle_data[1]) if isinstance(candle_data[1], (int, float)) else 0.0,
                            high=float(candle_data[3]) if isinstance(candle_data[3], (int, float)) else 0.0,
                            low=float(candle_data[4]) if isinstance(candle_data[4], (int, float)) else 0.0,
                            close=float(candle_data[2]) if isinstance(candle_data[2], (int, float)) else 0.0,
                            volume=float(candle_data[5]) if len(candle_data) > 5 and isinstance(candle_data[5], (int, float)) else 0.0,
                            asset=asset,
                            timeframe=timeframe,
                        )
                        candles.append(candle)

        except Exception as e:
            logger.error(f"Error parsing candles data: {e}")

        return candles

    async def _handle_candles_stream(self, data: Dict[str, Any]) -> None:
        """Handle candle data from stream updates (changeSymbol responses)"""
        try:
            asset = data.get("asset")
            period = data.get("period")
            logger.info(f"🕯️ _handle_candles_stream called - asset: {asset}, period: {period}")

            if not asset or not period:
                logger.warning(f"🕯️ Missing asset or period in stream data")
                return

            request_id = f"{asset}_{period}"
            logger.info(f"🕯️ Processing candle stream for {asset} ({period}s), request_id: {request_id}")

            if (
                hasattr(self, "_candle_requests")
                and request_id in self._candle_requests
            ):
                future = self._candle_requests[request_id]
                logger.info(f"🕯️ Found future for request {request_id}, done: {future.done()}")
                if not future.done():
                    candles = self._parse_stream_candles(data, asset, period)
                    logger.info(f"🕯️ Parsed {len(candles)} candles from stream")
                    if candles:
                        future.set_result(candles)
                    else:
                        logger.warning(f"🕯️ No candles parsed from stream data")
                else:
                    logger.warning(f"🕯️ Future for {request_id} already done")
                del self._candle_requests[request_id]
            else:
                logger.warning(f"🕯️ No pending request found for {request_id}")
                logger.info(f"🕯️ Active requests: {list(self._candle_requests.keys()) if hasattr(self, '_candle_requests') else []}")
        except Exception as e:
            logger.error(f"Error handling candles stream: {e}")
            import traceback
            logger.error(traceback.format_exc())

    def _parse_stream_candles(
        self, stream_data: Dict[str, Any], asset: str, timeframe: int
    ):
        """Parse candles from stream update data (changeSymbol response)"""
        candles = []
        try:
            logger.info(f"🕯️ _parse_stream_candles called for {asset}, keys: {list(stream_data.keys())}")
            candle_data = stream_data.get("data") or stream_data.get("candles") or []
            logger.info(f"🕯️ candle_data type: {type(candle_data)}, length: {len(candle_data) if isinstance(candle_data, list) else 'N/A'}")

            if isinstance(candle_data, list):
                for item in candle_data:
                    logger.info(f"🕯️ Processing candle item type: {type(item)}")
                    if isinstance(item, dict):
                        candle_time = item.get("time")
                        if candle_time is None:
                            logger.warning(f"🕯️ Candle missing time field")
                            continue
                        try:
                            candle = Candle(
                                timestamp=datetime.fromtimestamp(candle_time) if isinstance(candle_time, (int, float)) else datetime.now(),
                                open=float(item.get("open", 0)) if isinstance(item.get("open"), (int, float)) else 0.0,
                                high=float(item.get("high", 0)) if isinstance(item.get("high"), (int, float)) else 0.0,
                                low=float(item.get("low", 0)) if isinstance(item.get("low"), (int, float)) else 0.0,
                                close=float(item.get("close", 0)) if isinstance(item.get("close"), (int, float)) else 0.0,
                                volume=float(item.get("volume", 0)) if isinstance(item.get("volume"), (int, float)) else 0.0,
                                asset=asset,
                                timeframe=timeframe,
                            )
                            candles.append(candle)
                            logger.info(f"🕯️ Added candle: {candle}")
                        except (ValueError, TypeError) as e:
                            logger.warning(f"🕯️ Error creating candle: {e}")
                    else:
                        logger.warning(f"🕯️ Candle item is not dict: {item}")
            else:
                logger.warning(f"🕯️ candle_data is not a list: {type(candle_data)}")
        except Exception as e:
            logger.error(f"Error parsing stream candles: {e}")
            import traceback
            logger.error(traceback.format_exc())

        return candles

    async def _on_keep_alive_connected(self, data: Dict[str, Any]):
        """Handle keep-alive connection established"""
        pass

    async def _on_keep_alive_reconnected(self, data: Dict[str, Any]):
        """Handle keep-alive reconnection"""
        pass

    async def _on_keep_alive_message(self, data: Dict[str, Any]):
        """Handle keep-alive message received"""
        pass

    async def _emit_event(self, event: str, data: Any):
        """Emit event to registered callbacks"""
        if event in self._event_callbacks:
            for callback in self._event_callbacks[event]:
                try:
                    if asyncio.iscoroutinefunction(callback):
                        await callback(data)
                    else:
                        callback(data)
                except Exception as e:
                    logger.error(f"Error in event callback for {event}: {e}")
