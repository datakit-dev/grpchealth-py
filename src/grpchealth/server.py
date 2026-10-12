"""Adapts a `Checker`/`Watcher` to the generated `grpc.health.v1.Health` service.

Mirrors Go's `Register` (`grpchealth-go/grpchealth.go`): `mount_health_handler`
builds the `ConnectASGIApplication` for `grpc.health.v1.Health`, wired to
answer `Check`/`Watch` from a `Checker` you supply. If the `Checker` doesn't
also implement `Watcher`, `Watch` responds `Code.UNIMPLEMENTED`, same as Go.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from connectrpc.code import Code
from connectrpc.errors import ConnectError
from connectrpc.server import DEFAULT_READ_MAX_BYTES, ConnectASGIApplication

from grpchealth._gen.grpc.health.v1 import health_connect as _health_connect
from grpchealth._gen.grpc.health.v1 import health_pb as _health_pb
from grpchealth.checker import CheckRequest, Checker, Watcher

if TYPE_CHECKING:
    from collections.abc import AsyncIterator, Iterable

    from connectrpc.codec import Codec
    from connectrpc.compression import Compression
    from connectrpc.interceptor import Interceptor
    from connectrpc.request import RequestContext
    from protobuf import DescService


class HealthService:
    """Implements `grpc.health.v1.Health` over a `Checker`."""

    def __init__(self, checker: Checker) -> None:
        self._checker = checker
        self._watcher = checker if isinstance(checker, Watcher) else None

    async def check(
        self,
        request: _health_pb.HealthCheckRequest,
        ctx: RequestContext[
            _health_pb.HealthCheckRequest, _health_pb.HealthCheckResponse
        ],
        /,
    ) -> _health_pb.HealthCheckResponse:
        del ctx
        response = await self._checker.check(CheckRequest(service=request.service))
        return _health_pb.HealthCheckResponse(
            status=_health_pb.HealthCheckResponse.ServingStatus(response.status)
        )

    def watch(
        self,
        request: _health_pb.HealthCheckRequest,
        ctx: RequestContext[
            _health_pb.HealthCheckRequest, _health_pb.HealthCheckResponse
        ],
        /,
    ) -> AsyncIterator[_health_pb.HealthCheckResponse]:
        del ctx
        watcher = self._watcher
        if watcher is None:
            raise ConnectError(
                Code.UNIMPLEMENTED, "watching health state is not supported"
            )
        return self._watch(watcher, request.service)

    async def _watch(
        self, watcher: Watcher, service: str
    ) -> AsyncIterator[_health_pb.HealthCheckResponse]:
        async for response in watcher.watch(CheckRequest(service=service)):
            yield _health_pb.HealthCheckResponse(
                status=_health_pb.HealthCheckResponse.ServingStatus(response.status)
            )

    @classmethod
    def desc(cls) -> DescService:
        return _health_connect.Health.desc()


def mount_health_handler(
    checker: Checker,
    *,
    interceptors: Iterable[Interceptor] = (),
    read_max_bytes: int | None = DEFAULT_READ_MAX_BYTES,
    compressions: Iterable[Compression] | None = None,
    codecs: Iterable[Codec] | None = None,
) -> ConnectASGIApplication[Any]:
    """Builds the `grpc.health.v1.Health` ASGI application for `checker`.

    If `checker` also implements `Watcher`, the returned application supports
    the streaming `Watch` RPC; otherwise `Watch` responds `Code.UNIMPLEMENTED`.

    ```python
    health = mount_health_handler(StaticChecker("acme.user.v1.UserService"))
    app = Starlette(routes=[Mount(health.path, app=health)])
    ```
    """
    return _health_connect.HealthASGIApplication(
        HealthService(checker),
        interceptors=interceptors,
        read_max_bytes=read_max_bytes,
        compressions=compressions,
        codecs=codecs,
    )
