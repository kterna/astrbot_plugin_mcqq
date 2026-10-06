"""Latency and health probing module for Minecraft servers via TCP/RCON socket."""

import asyncio
import time
from typing import Dict, Optional, Tuple
from dataclasses import dataclass


@dataclass
class ProbeResult:
    server_name: str
    host: str
    port: int
    is_online: bool
    latency_ms: float
    error_message: Optional[str] = None


class ServerLatencyProbe:
    """Async latency and connection probe for multiple Minecraft server endpoints."""

    def __init__(self, default_timeout_sec: float = 3.0):
        self.default_timeout_sec = default_timeout_sec

    async def ping_server(
        self,
        server_name: str,
        host: str,
        port: int,
        timeout_sec: Optional[float] = None
    ) -> ProbeResult:
        timeout = timeout_sec or self.default_timeout_sec
        start_time = time.monotonic()
        try:
            # P0: Must strictly guard socket opening with timeout
            reader, writer = await asyncio.wait_for(
                asyncio.open_connection(host, port),
                timeout=timeout
            )
            elapsed_ms = (time.monotonic() - start_time) * 1000.0
            writer.close()
            await writer.wait_closed()
            return ProbeResult(
                server_name=server_name,
                host=host,
                port=port,
                is_online=True,
                latency_ms=round(elapsed_ms, 2)
            )
        except asyncio.TimeoutError:
            return ProbeResult(
                server_name=server_name,
                host=host,
                port=port,
                is_online=False,
                latency_ms=-1.0,
                error_message=f"Connection timed out after {timeout}s"
            )
        except Exception as e:
            return ProbeResult(
                server_name=server_name,
                host=host,
                port=port,
                is_online=False,
                latency_ms=-1.0,
                error_message=str(e)
            )

    async def probe_all(self, servers: Dict[str, Tuple[str, int]]) -> Dict[str, ProbeResult]:
        tasks = [
            self.ping_server(name, host, port)
            for name, (host, port) in servers.items()
        ]
        results = await asyncio.gather(*tasks, return_exceptions=False)
        return {res.server_name: res for res in results}
