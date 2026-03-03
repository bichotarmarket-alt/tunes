"""
Async WebSocket client for PocketOption API
"""

import asyncio
import json
import ssl
import time
from typing import Optional, Callable, Dict, Any, List, Deque, Union
from datetime import datetime
from collections import deque
import websockets
from websockets.exceptions import ConnectionClosed
from websockets.legacy.client import WebSocketClientProtocol
from loguru import logger

from .models import ConnectionInfo, ConnectionStatus, ServerTime
from .constants import CONNECTION_SETTINGS, DEFAULT_HEADERS
from .exceptions import WebSocketError, ConnectionError


class AsyncWebSocketClient:
    """Professional async WebSocket client for PocketOption"""

    def __init__(self):
        self.websocket: Optional[WebSocketClientProtocol] = None
        self.connection_info: Optional[ConnectionInfo] = None
        self.server_time: Optional[ServerTime] = None
        self._ping_task: Optional[asyncio.Task] = None
        self._receive_task: Optional[asyncio.Task] = None
        self._message_queue: asyncio.Queue = asyncio.Queue()
        self._event_handlers: Dict[str, List[Callable]] = {}
        self._running = False
        self._reconnect_attempts = 0
        self._max_reconnect_attempts = CONNECTION_SETTINGS["max_reconnect_attempts"]
        self._waiting_for_history_data = False

    async def connect(self, urls: List[str], ssid: str) -> bool:
        """
        Connect to PocketOption WebSocket with fallback URLs

        Args:
            urls: List of WebSocket URLs to try
            ssid: Session ID for authentication

        Returns:
            bool: True if connected successfully
        """
        for url in urls:
            try:
                logger.info(f"Attempting to connect to {url}")

                # SSL context setup
                ssl_context = ssl.SSLContext(ssl.PROTOCOL_TLS_CLIENT)
                ssl_context.check_hostname = False
                ssl_context.verify_mode = ssl.CERT_NONE

                # Connect with timeout
                ws = await asyncio.wait_for(
                    websockets.connect(
                        url,
                        ssl=ssl_context,
                        extra_headers=DEFAULT_HEADERS,
                        ping_interval=CONNECTION_SETTINGS["ping_interval"],
                        ping_timeout=CONNECTION_SETTINGS["ping_timeout"],
                        close_timeout=CONNECTION_SETTINGS["close_timeout"],
                    ),
                    timeout=10.0,
                )
                self.websocket = ws  # type: ignore
                
                # Update connection info
                region = self._extract_region_from_url(url)
                self.connection_info = ConnectionInfo(
                    url=url,
                    region=region,
                    status=ConnectionStatus.CONNECTED,
                    connected_at=datetime.now(),
                    reconnect_attempts=self._reconnect_attempts,
                )

                logger.info(f"Connected to {region} region successfully")
                
                # Start message handling
                self._running = True

                # Send initial handshake and wait for completion
                await self._send_handshake(ssid)

                # Start background tasks after handshake is complete
                await self._start_background_tasks()

                self._reconnect_attempts = 0
                return True

            except Exception as e:
                logger.warning(f"Failed to connect to {url}: {e}")
                if self.websocket:
                    await self.websocket.close()
                    self.websocket = None
                continue

        raise ConnectionError("Failed to connect to any WebSocket endpoint")

    async def disconnect(self):
        """Gracefully disconnect from WebSocket"""
        logger.info("Disconnecting from WebSocket")

        self._running = False

        # Cancel background tasks with timeout to avoid RecursionError
        tasks_to_cancel = []
        if self._ping_task and not self._ping_task.done():
            tasks_to_cancel.append(self._ping_task)
        if self._receive_task and not self._receive_task.done():
            tasks_to_cancel.append(self._receive_task)

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

        # Close WebSocket connection
        if self.websocket:
            await self.websocket.close()
            self.websocket = None

        # Update connection status
        if self.connection_info:
            self.connection_info = ConnectionInfo(
                url=self.connection_info.url,
                region=self.connection_info.region,
                status=ConnectionStatus.DISCONNECTED,
                connected_at=self.connection_info.connected_at,
                last_ping=self.connection_info.last_ping,
                reconnect_attempts=self.connection_info.reconnect_attempts,
            )

    async def send_message(self, message: str) -> None:
        """Send message to WebSocket"""
        if not self.websocket or self.websocket.closed:
            raise WebSocketError("WebSocket is not connected")

        try:
            await self.websocket.send(message)
            logger.debug(f"Sent message: {message}")
            
            # Registrar mensagem enviada no performance monitor (usando função global)
            try:
                from services.performance_monitor import record_ws_message_global
                record_ws_message_global(sent=True)
                logger.info("[WS TRACK] Mensagem enviada registrada")
            except Exception as e:
                logger.error(f"[WS TRACK] ERRO ao registrar mensagem enviada: {e}")
        except Exception as e:
            logger.error(f"Failed to send message: {e}")
            raise WebSocketError(f"Failed to send message: {e}")

    async def receive_messages(self) -> None:
        """Continuously receive and process messages"""
        try:
            while self._running and self.websocket:
                try:
                    message = await asyncio.wait_for(
                        self.websocket.recv(),
                        timeout=CONNECTION_SETTINGS["message_timeout"],
                    )
                    await self._process_message(message)

                except asyncio.TimeoutError:
                    logger.warning("Message receive timeout")
                    continue
                except ConnectionClosed:
                    logger.warning("WebSocket connection closed")
                    await self._handle_disconnect()
                    break

        except Exception as e:
            logger.error(f"Error in message receiving: {e}")
            await self._handle_disconnect()

    def add_event_handler(self, event: str, handler: Callable) -> None:
        """Add event handler"""
        if event not in self._event_handlers:
            self._event_handlers[event] = []
        self._event_handlers[event].append(handler)

    def remove_event_handler(self, event: str, handler: Callable) -> None:
        """Remove event handler"""
        if event in self._event_handlers:
            try:
                self._event_handlers[event].remove(handler)
            except ValueError:
                pass

    async def _send_handshake(self, ssid: str) -> None:
        """Send initial handshake messages"""
        try:
            # Wait for initial connection message
            initial_message = await asyncio.wait_for(
                self.websocket.recv(), timeout=10.0
            )
            logger.debug(f"Received initial: {initial_message}")

            # Ensure initial_message is a string
            if isinstance(initial_message, memoryview):
                initial_message = bytes(initial_message).decode("utf-8")
            elif isinstance(initial_message, (bytes, bytearray)):
                initial_message = initial_message.decode("utf-8")

            # Check if it's the expected initial message format
            if initial_message.startswith("0") and "sid" in initial_message:
                # Send "40" response
                await self.send_message("40")
                logger.debug("Sent '40' response")

                # Wait for connection establishment message
                conn_message = await asyncio.wait_for(
                    self.websocket.recv(), timeout=10.0
                )
                logger.debug(f"Received connection: {conn_message}")

                # Ensure conn_message is a string
                if isinstance(conn_message, memoryview):
                    conn_message_str = bytes(conn_message).decode("utf-8")
                elif isinstance(conn_message, (bytes, bytearray)):
                    conn_message_str = conn_message.decode("utf-8")
                else:
                    conn_message_str = conn_message

                if conn_message_str.startswith("40") and "sid" in conn_message_str:
                    # Send SSID authentication
                    await self.send_message(ssid)
                    logger.debug("Sent SSID authentication")
                else:
                    logger.warning(f"Unexpected connection message format: {conn_message}")
            else:
                logger.warning(f"Unexpected initial message format: {initial_message}")

            logger.debug("Handshake sequence completed")

        except asyncio.TimeoutError:
            logger.error("Handshake timeout - server didn't respond as expected")
            raise WebSocketError("Handshake timeout")
        except Exception as e:
            logger.error(f"Handshake failed: {e}")
            raise

    async def _start_background_tasks(self) -> None:
        """Start background tasks"""
        # Start ping task
        self._ping_task = asyncio.create_task(self._ping_loop())

        # Start message receiving task
        self._receive_task = asyncio.create_task(self.receive_messages())

    async def _ping_loop(self) -> None:
        """Send periodic ping messages"""
        while self._running and self.websocket:
            try:
                await asyncio.sleep(CONNECTION_SETTINGS["ping_interval"])

                if self.websocket and not self.websocket.closed:
                    await self.send_message('42["ps"]')

                    # Update last ping time
                    if self.connection_info:
                        self.connection_info = ConnectionInfo(
                            url=self.connection_info.url,
                            region=self.connection_info.region,
                            status=self.connection_info.status,
                            connected_at=self.connection_info.connected_at,
                            last_ping=datetime.now(),
                            reconnect_attempts=self.connection_info.reconnect_attempts,
                        )

            except Exception as e:
                logger.error(f"Ping failed: {e}")
                break

    async def _process_message(self, message) -> None:
        """Process incoming WebSocket message"""
        try:
            # Registrar mensagem recebida no performance monitor (usando função global)
            try:
                from services.performance_monitor import record_ws_message_global
                record_ws_message_global(sent=False)
                logger.info("[WS TRACK] Mensagem recebida registrada")
            except Exception as e:
                logger.error(f"[WS TRACK] ERRO ao registrar mensagem recebida: {e}")
            
            # Handle bytes messages first
            if isinstance(message, bytes):
                decoded_message = message.decode("utf-8")
                try:
                    # Try to parse as JSON
                    json_data = json.loads(decoded_message)
                    
                    # Check if this is history data (waiting for history data)
                    if self._waiting_for_history_data:
                        self._waiting_for_history_data = False
                        # Emit as candles_received event
                        await self._emit_event("candles_received", json_data)
                        return
                    
                    logger.debug(f"Received JSON bytes message: {json_data}")

                    # Handle balance data
                    if "balance" in json_data:
                        is_demo_value = json_data.get("isDemo", json_data.get("is_demo", 1))
                        balance_data = {
                            "balance": json_data["balance"],
                            "currency": "USD",
                            "isDemo": bool(is_demo_value),
                        }
                        if "uid" in json_data:
                            balance_data["uid"] = json_data["uid"]

                        logger.info(f"Balance data received: {balance_data}")
                        await self._emit_event("balance_data", balance_data)

                    # Handle order data
                    elif "requestId" in json_data and isinstance(json_data.get("requestId"), str):
                        await self._emit_event("order_data", json_data)

                    # Handle other JSON data
                    else:
                        await self._emit_event("json_data", json_data)

                except json.JSONDecodeError:
                    # If not JSON, treat as regular bytes message
                    logger.debug(f"Non-JSON bytes message: {decoded_message[:100]}...")

                return

            # Handle string messages
            if isinstance(message, str):
                logger.debug(f"Received message: {message}")

            # Handle different message types
            if message.startswith("0") and "sid" in message:
                await self.send_message("40")

            elif message == "2":
                await self.send_message("3")

            elif message.startswith("40") and "sid" in message:
                await self._emit_event("connected", {})

            elif message.startswith("451-["):
                # Parse JSON message
                json_part = message.split("-", 1)[1]
                data = json.loads(json_part)
                await self._handle_json_message(data)

            elif message.startswith("42") and "NotAuthorized" in message:
                logger.error(
                    "Authentication failed: Server rejected SSID. "
                    "Please verify your SSID is correct and not expired."
                )
                await self._emit_event("auth_error", {"message": "Invalid or expired SSID - Server returned NotAuthorized"})

        except Exception as e:
            logger.error(f"Error processing message: {e}")

    async def _handle_json_message(self, data: Union[List[Any], Dict[str, Any]]) -> None:
        """Handle JSON formatted messages"""
        if not data:
            return

        # Handle both list and dict formats
        if isinstance(data, dict):
            event_type = data.get("type", data.get("event", "unknown"))
            event_data = data.get("data", data)
        elif isinstance(data, list) and len(data) > 0:
            event_type = data[0]
            event_data = data[1] if len(data) > 1 else {}
        else:
            return

        # Handle specific events
        if event_type == "successauth":
            await self._emit_event("authenticated", event_data)

        elif event_type == "successupdateBalance":
            await self._emit_event("balance_updated", event_data)

        elif event_type == "successopenOrder":
            await self._emit_event("order_opened", event_data)

        elif event_type == "successcloseOrder":
            await self._emit_event("order_closed", event_data)

        elif event_type == "updateStream":
            await self._emit_event("stream_update", event_data)

        elif event_type == "loadHistoryPeriod":
            await self._emit_event("candles_received", event_data)

        elif event_type == "updateHistoryNew":
            await self._emit_event("history_update", event_data)

        elif event_type == "updateHistoryNewFast":
            # Esta é uma mensagem de controle, os dados reais vêm na próxima mensagem binária
            self._waiting_for_history_data = True
            return

        elif event_type == "updateAssets":
            await self._emit_event("assets_update", event_data)

        elif event_type == "updateClosedDeals":
            await self._emit_event("update_closed_deals", event_data)

        else:
            await self._emit_event(
                "unknown_event", {"type": event_type, "data": event_data}
            )

    async def _emit_event(self, event: str, data: Any) -> None:
        """Emit event to registered handlers"""
        if event in self._event_handlers:
            for handler in self._event_handlers[event]:
                try:
                    if asyncio.iscoroutinefunction(handler):
                        await handler(data)
                    elif callable(handler):
                        handler(data)
                except Exception as e:
                    logger.error(f"Error in event handler for {event}: {e}")

    async def _handle_disconnect(self) -> None:
        """Handle WebSocket disconnection"""
        if self.connection_info:
            self.connection_info = ConnectionInfo(
                url=self.connection_info.url,
                region=self.connection_info.region,
                status=ConnectionStatus.DISCONNECTED,
                connected_at=self.connection_info.connected_at,
                last_ping=self.connection_info.last_ping,
                reconnect_attempts=self.connection_info.reconnect_attempts,
            )

        await self._emit_event("disconnected", {})

    def _extract_region_from_url(self, url: str) -> str:
        """Extract region name from URL"""
        try:
            if "//" not in url:
                return "UNKNOWN"
            parts = url.split("//")[1].split(".")[0]
            if "api-" in parts:
                return parts.replace("api-", "").upper()
            elif "demo" in parts:
                return "DEMO"
            else:
                return "UNKNOWN"
        except Exception:
            return "UNKNOWN"

    @property
    def is_connected(self) -> bool:
        """Check if WebSocket is connected"""
        return (
            self.websocket is not None
            and not self.websocket.closed
            and self.connection_info is not None
            and self.connection_info.status == ConnectionStatus.CONNECTED
        )
