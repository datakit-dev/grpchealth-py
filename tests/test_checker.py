"""Unit tests for `Status`, `CheckRequest`/`CheckResponse`, and `StaticChecker`."""

from __future__ import annotations

import asyncio

import pytest
from connectrpc.code import Code
from connectrpc.errors import ConnectError

from grpchealth.checker import CheckRequest, StaticChecker, Status


async def test_check_reports_serving_for_registered_service() -> None:
    checker = StaticChecker("acme.user.v1.UserService")
    response = await checker.check(CheckRequest(service="acme.user.v1.UserService"))
    assert response.status is Status.SERVING


async def test_check_reports_serving_for_whole_process_by_default() -> None:
    checker = StaticChecker("acme.user.v1.UserService")
    response = await checker.check(CheckRequest())
    assert response.status is Status.SERVING


async def test_check_raises_not_found_for_unregistered_service() -> None:
    checker = StaticChecker("acme.user.v1.UserService")
    with pytest.raises(ConnectError) as exc_info:
        await checker.check(CheckRequest(service="unknown.Service"))
    assert exc_info.value.code is Code.NOT_FOUND


async def test_set_status_updates_check_result() -> None:
    checker = StaticChecker("acme.user.v1.UserService")
    checker.set_status("acme.user.v1.UserService", Status.NOT_SERVING)
    response = await checker.check(CheckRequest(service="acme.user.v1.UserService"))
    assert response.status is Status.NOT_SERVING


async def test_set_status_registers_new_services() -> None:
    checker = StaticChecker()
    checker.set_status("acme.user.v1.UserService", Status.NOT_SERVING)
    response = await checker.check(CheckRequest(service="acme.user.v1.UserService"))
    assert response.status is Status.NOT_SERVING


async def test_set_status_with_empty_service_sets_process_wide_status() -> None:
    checker = StaticChecker()
    checker.set_status("", Status.NOT_SERVING)
    response = await checker.check(CheckRequest())
    assert response.status is Status.NOT_SERVING


async def test_watch_yields_current_status_immediately() -> None:
    checker = StaticChecker("acme.user.v1.UserService")
    watch = checker.watch(CheckRequest(service="acme.user.v1.UserService"))
    response = await anext(watch)
    assert response.status is Status.SERVING
    await watch.aclose()


async def test_watch_raises_not_found_for_unregistered_service() -> None:
    checker = StaticChecker("acme.user.v1.UserService")
    with pytest.raises(ConnectError) as exc_info:
        await anext(checker.watch(CheckRequest(service="unknown.Service")))
    assert exc_info.value.code is Code.NOT_FOUND


async def test_watch_yields_again_when_status_changes() -> None:
    checker = StaticChecker("acme.user.v1.UserService")
    watch = checker.watch(CheckRequest(service="acme.user.v1.UserService"))
    try:
        first = await anext(watch)
        assert first.status is Status.SERVING

        async def flip_after_yield() -> None:
            await asyncio.sleep(0)
            checker.set_status("acme.user.v1.UserService", Status.NOT_SERVING)

        asyncio.create_task(flip_after_yield())
        second = await anext(watch)
        assert second.status is Status.NOT_SERVING
    finally:
        await watch.aclose()


async def test_watch_does_not_repeat_unchanged_status() -> None:
    checker = StaticChecker("acme.user.v1.UserService")
    watch = checker.watch(CheckRequest(service="acme.user.v1.UserService"))
    try:
        first = await anext(watch)
        assert first.status is Status.SERVING

        # Setting the same status again shouldn't produce a second event.
        checker.set_status("acme.user.v1.UserService", Status.SERVING)
        checker.set_status("acme.user.v1.UserService", Status.NOT_SERVING)
        second = await anext(watch)
        assert second.status is Status.NOT_SERVING
    finally:
        await watch.aclose()
