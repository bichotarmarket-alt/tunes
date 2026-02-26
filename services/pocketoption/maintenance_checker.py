from __future__ import annotations

import asyncio
from datetime import datetime
from typing import Callable, Optional, List

import httpx
from loguru import logger

from core.config import settings
from services.pocketoption.constants import DEFAULT_HEADERS


class MaintenanceChecker:
    def __init__(self) -> None:
        self._is_under_maintenance = False
        self._last_checked_at: Optional[datetime] = None
        self._task: Optional[asyncio.Task] = None
        self._maintenance_start_callbacks: List[Callable] = []
        self._maintenance_end_callbacks: List[Callable] = []

    @property
    def is_under_maintenance(self) -> bool:
        return self._is_under_maintenance

    @property
    def last_checked_at(self) -> Optional[datetime]:
        return self._last_checked_at

    def on_maintenance_start(self, callback: Callable) -> None:
        """Registrar callback para quando manutenção for detectada"""
        self._maintenance_start_callbacks.append(callback)

    def on_maintenance_end(self, callback: Callable) -> None:
        """Registrar callback para quando manutenção terminar"""
        self._maintenance_end_callbacks.append(callback)

    async def start(self) -> None:
        if self._task and not self._task.done():
            return
        await self._check_once()
        self._task = asyncio.create_task(self._check_loop())

    async def stop(self) -> None:
        if self._task and not self._task.done():
            self._task.cancel()
            try:
                await asyncio.wait_for(self._task, timeout=5.0)
            except asyncio.TimeoutError:
                logger.debug("[MaintenanceChecker] Timeout ao aguardar finalização da task")
            except asyncio.CancelledError:
                logger.info("[MaintenanceChecker] Task canceled")

    async def _check_loop(self) -> None:
        while True:
            await asyncio.sleep(settings.POCKETOPTION_MAINTENANCE_CHECK_INTERVAL)
            await self._check_once()

    async def _check_once(self) -> None:
        url = settings.POCKETOPTION_MAINTENANCE_CHECK_URL
        timeout = settings.POCKETOPTION_MAINTENANCE_CHECK_TIMEOUT
        headers = dict(DEFAULT_HEADERS)
        headers.setdefault("Accept", "text/html,application/xhtml+xml")
        try:
            async with httpx.AsyncClient(
                headers=headers,
                follow_redirects=True,
                timeout=timeout,
            ) as client:
                response = await client.get(url)
            html = response.text if response else ""
            is_maintenance = self._detect_maintenance(response.status_code, html)
            self._last_checked_at = datetime.utcnow()
        except Exception as exc:
            logger.warning(f"[MaintenanceChecker] Failed to check maintenance: {exc}")
            return

        if is_maintenance != self._is_under_maintenance:
            self._is_under_maintenance = is_maintenance
            if is_maintenance:
                logger.warning(
                    "[MaintenanceChecker] Maintenance detected. Blocking trades."
                )
                # Executar callbacks de início de manutenção
                for callback in self._maintenance_start_callbacks:
                    try:
                        if asyncio.iscoroutinefunction(callback):
                            await callback()
                        else:
                            callback()
                    except Exception as exc:
                        logger.error(f"[MaintenanceChecker] Error in maintenance_start callback: {exc}")
            else:
                logger.info("[MaintenanceChecker] Maintenance cleared. Trades allowed.")
                # Executar callbacks de fim de manutenção
                for callback in self._maintenance_end_callbacks:
                    try:
                        if asyncio.iscoroutinefunction(callback):
                            await callback()
                        else:
                            callback()
                    except Exception as exc:
                        logger.error(f"[MaintenanceChecker] Error in maintenance_end callback: {exc}")

    def _detect_maintenance(self, status_code: int, html: str) -> bool:
        if not html:
            return False
        html_lower = html.lower()
        if "<title>server maintenance</title>" in html_lower:
            return True
        if 'class="maintenance"' in html_lower:
            return True
        if "scheduled technical maintenance" in html_lower:
            return True
        return False


maintenance_checker = MaintenanceChecker()
