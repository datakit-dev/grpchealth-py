"""Shared fixtures for the health integration tests."""

from __future__ import annotations

from typing import TYPE_CHECKING

import pytest
from pyvoy import PyvoyServer

if TYPE_CHECKING:
    from collections.abc import AsyncIterator


async def _address_for(app: str) -> AsyncIterator[str]:
    async with PyvoyServer(app, log_level="error") as server:
        yield f"http://127.0.0.1:{server.listener_port}"


@pytest.fixture
async def watchable_address() -> AsyncIterator[str]:
    async for address in _address_for("tests.live_app:app"):
        yield address


@pytest.fixture
async def unwatchable_address() -> AsyncIterator[str]:
    async for address in _address_for("tests.live_app:unwatchable_app"):
        yield address
