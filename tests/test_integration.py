"""End-to-end coverage of `mount_health_handler` + `Client` over the wire, via pyvoy."""

from __future__ import annotations

import pytest
from connectrpc.code import Code
from connectrpc.errors import ConnectError

from grpchealth import CheckRequest, Client, Status
from tests.live_app import SERVICE


async def test_check_reports_whole_process_status(watchable_address: str) -> None:
    async with Client(watchable_address) as client:
        response = await client.check(CheckRequest())
    assert response.status is Status.SERVING


async def test_check_reports_known_service_status(watchable_address: str) -> None:
    async with Client(watchable_address) as client:
        response = await client.check(CheckRequest(service=SERVICE))
    assert response.status is Status.SERVING


async def test_check_raises_not_found_for_unknown_service(
    watchable_address: str,
) -> None:
    async with Client(watchable_address) as client:
        with pytest.raises(ConnectError) as exc_info:
            await client.check(CheckRequest(service="unknown.Service"))
    assert exc_info.value.code is Code.NOT_FOUND


async def test_watch_yields_current_status_immediately(watchable_address: str) -> None:
    async with Client(watchable_address) as client:
        responses = client.watch(CheckRequest(service=SERVICE))
        try:
            first = await anext(responses)
            assert first.status is Status.SERVING
        finally:
            await responses.aclose()


async def test_watch_raises_unimplemented_without_a_watcher(
    unwatchable_address: str,
) -> None:
    async with Client(unwatchable_address) as client:
        with pytest.raises(ConnectError) as exc_info:
            await anext(client.watch(CheckRequest()))
    assert exc_info.value.code is Code.UNIMPLEMENTED
