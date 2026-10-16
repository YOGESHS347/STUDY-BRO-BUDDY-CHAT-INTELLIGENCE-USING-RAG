"""
High-performance asynchronous TCP relay proxy forwarding 127.0.0.1:6379 to WSL2 Linux Redis.
Enables seamless Windows local development with standard redis://localhost:6379/0 URLs.
"""

import asyncio
import sys

WSL_HOST = "172.24.36.112"
WSL_PORT = 6379
LOCAL_HOST = "127.0.0.1"
LOCAL_PORT = 6379


async def pipe(reader: asyncio.StreamReader, writer: asyncio.StreamWriter) -> None:
    try:
        while not reader.at_eof():
            data = await reader.read(65536)
            if not data:
                break
            writer.write(data)
            await writer.drain()
    except Exception:
        pass
    finally:
        try:
            writer.close()
            await writer.wait_closed()
        except Exception:
            pass


async def handle_connection(client_reader: asyncio.StreamReader, client_writer: asyncio.StreamWriter) -> None:
    try:
        remote_reader, remote_writer = await asyncio.open_connection(WSL_HOST, WSL_PORT)
        await asyncio.gather(
            pipe(client_reader, remote_writer),
            pipe(remote_reader, client_writer),
            return_exceptions=True,
        )
    except Exception:
        try:
            client_writer.close()
            await client_writer.wait_closed()
        except Exception:
            pass


async def main() -> None:
    server = await asyncio.start_server(handle_connection, LOCAL_HOST, LOCAL_PORT)
    print(f"[REDIS PROXY] Listening on {LOCAL_HOST}:{LOCAL_PORT} -> {WSL_HOST}:{WSL_PORT}", flush=True)
    async with server:
        await server.serve_forever()


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("[REDIS PROXY] Stopped.", flush=True)
        sys.exit(0)
