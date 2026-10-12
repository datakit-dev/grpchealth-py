"""Client for the gRPC health-checking API.

Modeled on Go's `Client` (`grpchealth-go/client.go`): wraps the generated
`HealthClient`, translating its wire-format request/response messages to and
from `CheckRequest`/`CheckResponse`, so a `Client` instance structurally
satisfies `Checker` (and, via `watch`, `Watcher`) and can be used anywhere
either is expected -- for example, to proxy another server's health status
through your own.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from grpchealth._gen.grpc.health.v1 import health_connect as _health_connect
from grpchealth._gen.grpc.health.v1 import health_pb as _health_pb
from grpchealth.checker import CheckRequest, CheckResponse, Status

if TYPE_CHECKING:
    from collections.abc import AsyncIterator

    from connectrpc.request import Headers


class Client:
    """Calls the gRPC health-checking API against one server.

    By default, transports use the Connect protocol with the binary Protobuf
    codec; accepts the same keyword options as `connectrpc.client.ConnectClient`
    to configure the gRPC protocol or otherwise.
    """

    def __init__(self, address: str, **client_options: Any) -> None:
        self._client = _health_connect.HealthClient(address, **client_options)

    async def check(
        self,
        request: CheckRequest,
        *,
        headers: Headers | None = None,
        timeout_ms: int | None = None,
    ) -> CheckResponse:
        """Reports the health of `request.service`.

        An empty `request.service` asks for the health of the whole server
        process. If the service is unknown, raises a `ConnectError` with
        `Code.NOT_FOUND`.
        """
        response = await self._client.check(
            _health_pb.HealthCheckRequest(service=request.service),
            headers=headers,
            timeout_ms=timeout_ms,
        )
        return CheckResponse(status=Status(response.status))

    async def watch(
        self,
        request: CheckRequest,
        *,
        headers: Headers | None = None,
        timeout_ms: int | None = None,
    ) -> AsyncIterator[CheckResponse]:
        """Streams health status changes for `request.service`.

        Yields the current status immediately, then again each time it may
        have changed. The stream ends when the server closes it or an error
        occurs -- including `Code.UNIMPLEMENTED` if the server doesn't
        support `Watch`.
        """
        async for response in self._client.watch(
            _health_pb.HealthCheckRequest(service=request.service),
            headers=headers,
            timeout_ms=timeout_ms,
        ):
            yield CheckResponse(status=Status(response.status))

    async def close(self) -> None:
        await self._client.close()

    async def __aenter__(self) -> Client:
        return self

    async def __aexit__(self, *exc_info: object) -> None:
        await self.close()
