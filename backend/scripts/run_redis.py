"""
Local TCP Redis server for development and testing.
Uses fakeredis.TcpFakeServer to provide a standard RESP Redis server on 127.0.0.1:6379
without requiring Docker or external services.
"""

import signal
import sys
import time
import fakeredis

HOST = "127.0.0.1"
PORT = 6379


def main():
    print(f"[LOCAL REDIS] Starting Redis TCP server on {HOST}:{PORT}...", flush=True)
    try:
        server = fakeredis.TcpFakeServer((HOST, PORT))
    except Exception as exc:
        print(f"[LOCAL REDIS] Could not bind {HOST}:{PORT}: {exc}", flush=True)
        sys.exit(1)

    def handle_signal(sig, frame):
        print("\n[LOCAL REDIS] Shutting down Redis server...", flush=True)
        server.shutdown()
        server.server_close()
        sys.exit(0)

    signal.signal(signal.SIGINT, handle_signal)
    signal.signal(signal.SIGTERM, handle_signal)

    print(f"[LOCAL REDIS] Ready to accept connections at redis://{HOST}:{PORT}/0", flush=True)
    try:
        server.serve_forever()
    except Exception as e:
        print(f"[LOCAL REDIS] Server stopped: {e}", flush=True)
    finally:
        server.server_close()


if __name__ == "__main__":
    main()
