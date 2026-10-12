# grpchealth-py

An idiomatic Python implementation of [gRPC's health checking protocol][grpc-health]
(`grpc.health.v1`), built on [`protobuf-py`][protobuf-py] and
[`connectrpc`][connect-python]. Modeled on Buf's Go reference implementation,
[`grpchealth-go`][grpchealth-go].

Since the health service here is just a `ConnectASGIApplication` like any
other, it works over whichever of `connectrpc`'s protocols your own services
already speak -- Connect, gRPC, and gRPC-Web -- with no extra configuration.

[grpc-health]: https://github.com/grpc/grpc/blob/master/doc/health-checking.md
[protobuf-py]: https://github.com/bufbuild/protobuf-py
[connect-python]: https://github.com/connectrpc/connect-py
[grpchealth-go]: https://github.com/connectrpc/grpchealth-go

## Install

```sh
uv add grpchealth-py
```

## Usage

`mount_health_handler()` takes a `Checker` -- optionally one that also
implements `Watcher`, to support the streaming `Watch` RPC -- and returns a
ready-to-mount `ConnectASGIApplication`:

```python
from starlette.applications import Starlette
from starlette.routing import Mount
from grpchealth.checker import StaticChecker
from grpchealth.server import mount_health_handler

health = mount_health_handler(StaticChecker("acme.greet.v1.GreetService"))

app = Starlette(routes=[Mount(health.path, app=health)])
```

`Watch` is a server-streaming RPC, which benefits from an HTTP/2-capable ASGI
server. As of this writing, [`pyvoy`][pyvoy] is the server most reliably
passing the Connect conformance suite's HTTP/2 and streaming tests, so it's
the recommended way to serve `app` above:

```python
import asyncio
import pyvoy

async def main() -> None:
    server = pyvoy.PyvoyServer("myapp:app", port=8080)
    await server.start()
    await server.wait()

asyncio.run(main())
```

You aren't required to use `pyvoy` -- any ASGI server with working HTTP/2 and
streaming support will do -- but not every ASGI server reliably supports both
today.

[pyvoy]: https://github.com/curioswitch/pyvoy

## Client

`Client` calls the gRPC health-checking API against a server. It structurally
satisfies `Checker` (and, via `watch`, `Watcher`), so it can be used anywhere
either is expected:

```python
import asyncio

from grpchealth.checker import CheckRequest
from grpchealth.client import Client


async def main() -> None:
    async with Client("http://localhost:8080") as client:
        response = await client.check(CheckRequest(service="acme.greet.v1.GreetService"))
        print(response.status)

        async for response in client.watch(CheckRequest(service="acme.greet.v1.GreetService")):
            print(response.status)


asyncio.run(main())
```

## Development

```sh
uv run -- buf generate   # regenerate src/grpchealth/_gen from the upstream schema
uv run pytest
```
