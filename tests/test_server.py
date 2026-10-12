"""Unit tests for `HealthService`, the `Checker`/`Watcher`-to-`Health` adapter."""

from __future__ import annotations

import pytest
from connectrpc.code import Code
from connectrpc.errors import ConnectError

from grpchealth._gen.grpc.health.v1 import health_pb
from grpchealth.checker import CheckRequest, CheckResponse, Status
from grpchealth.server import HealthService


class _StubChecker:
    def __init__(self, status: Status = Status.SERVING) -> None:
        self.status = status
        self.requests: list[CheckRequest] = []

    async def check(self, request: CheckRequest) -> CheckResponse:
        self.requests.append(request)
        if request.service == "unknown.Service":
            raise ConnectError(Code.NOT_FOUND, f"unknown service {request.service}")
        return CheckResponse(status=self.status)


class _StubWatcher(_StubChecker):
    async def watch(self, request: CheckRequest):  # noqa: ANN201
        yield CheckResponse(status=self.status)


async def test_check_converts_request_and_response() -> None:
    checker = _StubChecker(status=Status.NOT_SERVING)
    service = HealthService(checker)
    response = await service.check(
        health_pb.HealthCheckRequest(service="acme.user.v1.UserService"), None
    )
    assert checker.requests == [CheckRequest(service="acme.user.v1.UserService")]
    assert response.status is health_pb.HealthCheckResponse.ServingStatus.NOT_SERVING


async def test_check_propagates_checker_errors() -> None:
    service = HealthService(_StubChecker())
    with pytest.raises(ConnectError) as exc_info:
        await service.check(
            health_pb.HealthCheckRequest(service="unknown.Service"), None
        )
    assert exc_info.value.code is Code.NOT_FOUND


async def test_watch_raises_unimplemented_without_a_watcher() -> None:
    service = HealthService(_StubChecker())
    with pytest.raises(ConnectError) as exc_info:
        service.watch(health_pb.HealthCheckRequest(), None)
    assert exc_info.value.code is Code.UNIMPLEMENTED


async def test_watch_streams_converted_responses_for_a_watcher() -> None:
    service = HealthService(_StubWatcher(status=Status.SERVING))
    responses = [
        response
        async for response in service.watch(
            health_pb.HealthCheckRequest(service="acme.user.v1.UserService"), None
        )
    ]
    assert [r.status for r in responses] == [
        health_pb.HealthCheckResponse.ServingStatus.SERVING
    ]


async def test_desc_returns_the_health_service_descriptor() -> None:
    desc = HealthService.desc()
    assert desc.type_name == "grpc.health.v1.Health"
