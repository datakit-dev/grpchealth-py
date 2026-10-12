"""Health status types and the `Checker`/`Watcher` protocols implementations satisfy.

Modeled on Go's `Checker`/`Watcher`/`StaticChecker`
(`grpchealth-go/grpchealth.go`, `grpchealth-go/static_checker.go`), but with
Go's callback-plus-stop-function `Watch` replaced by a plain async generator:
`Watcher.watch()` is an `AsyncIterator` that yields the current status
immediately, then again each time it may have changed.
"""

from __future__ import annotations

import asyncio
from dataclasses import dataclass
from enum import IntEnum
from typing import TYPE_CHECKING, Protocol, runtime_checkable

from connectrpc.code import Code
from connectrpc.errors import ConnectError

if TYPE_CHECKING:
    from collections.abc import AsyncIterator


class Status(IntEnum):
    """The serving status of a service, or of the whole process.

    Mirrors `grpc.health.v1.HealthCheckResponse.ServingStatus`. `SERVICE_UNKNOWN`
    is only ever seen in a `Watch` reply for a service that isn't known; a
    `Checker` itself should never return it from `check()`.
    """

    UNKNOWN = 0
    SERVING = 1
    NOT_SERVING = 2
    SERVICE_UNKNOWN = 3


@dataclass(frozen=True, slots=True)
class CheckRequest:
    """A request for the health of a service.

    An empty `service` asks for the health of the whole process.
    """

    service: str = ""


@dataclass(frozen=True, slots=True)
class CheckResponse:
    """Reports the health of a service (or of the whole process)."""

    status: Status


@runtime_checkable
class Checker(Protocol):
    """Reports the health of a service. Must be safe to call concurrently."""

    async def check(self, request: CheckRequest) -> CheckResponse:
        """Returns the health of `request.service`.

        If the service is unknown, raises a `ConnectError` with `Code.NOT_FOUND`.
        """
        ...


@runtime_checkable
class Watcher(Checker, Protocol):
    """Extends `Checker` with the ability to stream status changes.

    `watch()` yields the current status immediately, then again each time it
    may have changed; it raises a `ConnectError` with `Code.NOT_FOUND` if
    `request.service` is unknown.
    """

    def watch(self, request: CheckRequest) -> AsyncIterator[CheckResponse]:
        """Streams `request.service`'s status until the caller stops iterating."""
        ...


class StaticChecker:
    """A simple `Checker`/`Watcher`.

    Always reports `Status.SERVING` for the whole process, and a static,
    settable status for each service named at construction (or later, via
    `set_status`).

    If you have a dynamic list of services, want to ping a database as part
    of your health check, or otherwise need something more specialized,
    write your own `Checker`.
    """

    def __init__(self, *services: str) -> None:
        self._statuses: dict[str, Status] = dict.fromkeys(services, Status.SERVING)
        self._events: dict[str, asyncio.Event] = {}

    def set_status(self, service: str, status: Status) -> None:
        """Sets `service`'s health status, registering it if necessary.

        An empty `service` sets the server-wide status returned to checks
        that don't name a particular service (absent that, such checks
        report `Status.SERVING`).
        """
        self._statuses[service] = status
        event = self._events.get(service)
        if event is not None:
            event.set()

    async def check(self, request: CheckRequest) -> CheckResponse:
        status = self._statuses.get(request.service)
        if status is not None:
            return CheckResponse(status=status)
        if not request.service:
            return CheckResponse(status=Status.SERVING)
        raise ConnectError(Code.NOT_FOUND, f"unknown service {request.service}")

    async def watch(self, request: CheckRequest) -> AsyncIterator[CheckResponse]:
        if request.service and request.service not in self._statuses:
            raise ConnectError(Code.NOT_FOUND, f"unknown service {request.service}")
        # Shared per-service, so `set_status` only has to wake whoever's watching it.
        event = self._events.setdefault(request.service, asyncio.Event())
        last: Status | None = None
        while True:
            # Cleared before reading status so a concurrent `set_status` is never missed.
            event.clear()
            status = self._statuses.get(request.service, Status.SERVING)
            if status != last:
                last = status
                yield CheckResponse(status=status)
            else:
                await event.wait()
