"""ASGI apps `pyvoy` mounts by import string for the integration tests.

These run in a separate Envoy-managed process, so they can't share state with
the test process -- each app is self-contained and its behavior is asserted
purely from the wire.
"""

from __future__ import annotations

from grpchealth import CheckRequest, CheckResponse, StaticChecker, Status
from grpchealth.server import mount_health_handler

SERVICE = "acme.user.v1.UserService"

app = mount_health_handler(StaticChecker(SERVICE))


class CheckOnlyChecker:
    """A `Checker` that doesn't implement `Watcher`."""

    async def check(self, request: CheckRequest) -> CheckResponse:
        del request
        return CheckResponse(status=Status.SERVING)


unwatchable_app = mount_health_handler(CheckOnlyChecker())
