import asyncio
import json
import threading
from collections import deque
from typing import Awaitable, Callable, Dict, Optional, Tuple
from urllib.parse import unquote_plus

from core.utils.player_cache import PlayerListCache
from core.managers.watchdog import WebSocketWatchdog
from core.routing.alert_dispatcher import AlertDispatcher, AlertPayload, AlertSeverity

import websockets
from astrbot import logger


# 共享反向 WebSocket 服务端：(host, port) -> SharedReverseServer
_SHARED_SERVERS: Dict[Tuple[str, int], "SharedReverseServer"] = {}
_SHARED_LOCK = threading.RLock()


class SharedReverseServer:
    """可被多个适配器共用的反向 WebSocket 服务端，按 x-self-name 路由。"""

    def __init__(self, host: str, port: int, path: str,
                 ping_interval: float = 30, ping_timeout: float = 10):
        self.ping_interval = ping_interval
        self.ping_timeout = ping_timeout
        self.host = host
        self.port = port
        self.path = path if path.startswith("/") else f"/{path}"
        self.ws_server = None
        self._running = False
        # server_name -> WebSocketManager (server mode)
        self.managers: Dict[str, "WebSocketManager"] = {}
        self._serve_task: Optional[asyncio.Task] = None

    def register(self, server_name: str, manager: "WebSocketManager"):
        self.managers[server_name] = manager
        logger.info(
            f"反向 WS 注册 server_name={server_name} -> "
            f"ws://{self.host}:{self.port}{self.path}"
        )

    def unregister(self, server_name: str):
        self.managers.pop(server_name, None)

    @property
    def is_empty(self) -> bool:
        return len(self.managers) == 0

    async def start(self):
        if self._running:
            return
        try:
            self.ws_server = await websockets.serve(
                self._handle_connection,
                self.host,
                self.port,
                process_request=self._process_request,
                ping_interval=self.ping_interval,
                ping_timeout=self.ping_timeout,
                close_timeout=1,
            )
            self._running = True
            logger.info(
                f"反向 WebSocket 服务端已启动: "
                f"ws://{self.host}:{self.port}{self.path}"
            )
        except OSError as e:
            logger.error(
                f"反向 WebSocket 服务端启动失败 "
                f"({self.host}:{self.port}): {e}"
            )
            raise

    async def stop(self):
        if not self._running:
            return
        self._running = False
        if self.ws_server is not None:
            self.ws_server.close()
            try:
                await asyncio.wait_for(self.ws_server.wait_closed(), timeout=5)
            except asyncio.TimeoutError:
                logger.warning("等待反向 WebSocket 服务端关闭超时")
            self.ws_server = None
        logger.info(
            f"反向 WebSocket 服务端已停止: {self.host}:{self.port}"
        )

    def _get_header(self, headers, name: str) -> Optional[str]:
        """兼容不同 websockets 版本的 header 读取。"""
        if headers is None:
            return None
        # websockets Headers 支持大小写不敏感 get
        try:
            value = headers.get(name)
            if value is not None:
                return value
        except Exception:
            pass
        try:
            value = headers.get(name.lower())
            if value is not None:
                return value
        except Exception:
            pass
        # 兼容 dict / list
        if isinstance(headers, dict):
            for k, v in headers.items():
                if str(k).lower() == name.lower():
                    return v
        return None

    async def _process_request(self, connection, request):
        """握手阶段校验 path / 鉴权 / server_name。"""
        path = getattr(request, "path", None) or getattr(connection, "path", "")
        # 去掉 query
        if path and "?" in path:
            path = path.split("?", 1)[0]

        if path != self.path:
            logger.warning(
                f"反向 WS 路径不匹配: 期望 {self.path}, 实际 {path}"
            )
            return connection.respond(404, "Invalid path")

        headers = getattr(request, "headers", None)
        self_name_raw = self._get_header(headers, "x-self-name")
        if not self_name_raw:
            logger.warning("反向 WS 缺少 x-self-name Header")
            return connection.respond(400, "Missing X-Self-Name Header")

        self_name = unquote_plus(self_name_raw)

        # 拒绝来自 astrbot 自身的回环连接
        origin = self._get_header(headers, "x-client-origin")
        if origin and origin.lower() == "astrbot":
            logger.warning("反向 WS 拒绝 x-client-origin=astrbot 的连接")
            return connection.respond(403, "X-Client-Origin cannot be astrbot")

        manager = self.managers.get(self_name)
        if manager is None:
            logger.warning(
                f"反向 WS 未知 server_name={self_name}，"
                f"已注册: {list(self.managers.keys())}"
            )
            return connection.respond(404, f"Unknown server_name: {self_name}")

        # 鉴权
        expected = manager.access_token
        if expected:
            auth = self._get_header(headers, "Authorization") or ""
            token = auth[7:] if auth.startswith("Bearer ") else auth
            if token != expected:
                logger.warning(f"反向 WS 鉴权失败: server_name={self_name}")
                return connection.respond(401, "Invalid access token")

        # 若已有连接，拒绝重复（由 manager 决定是否替换）
        if manager.connected and not manager.allow_replace_connection:
            logger.warning(f"反向 WS 重复连接: server_name={self_name}")
            return connection.respond(409, "Duplicate connection")

        return None  # 允许握手

    async def _handle_connection(self, websocket):
        headers = getattr(websocket, "request_headers", None)
        if headers is None and hasattr(websocket, "request"):
            headers = getattr(websocket.request, "headers", None)

        self_name_raw = self._get_header(headers, "x-self-name") or ""
        self_name = unquote_plus(self_name_raw)
        manager = self.managers.get(self_name)
        if manager is None:
            logger.warning(f"反向 WS 连接后找不到 manager: {self_name}")
            await websocket.close(1008, "Unknown server")
            return

        remote = getattr(websocket, "remote_address", None)
        logger.info(
            f"反向 WS 客户端已连接: server_name={self_name}, remote={remote}"
        )
        await manager._on_server_client_connected(websocket)


class WebSocketManager:
    """WebSocket 连接管理器。

    支持两种模式：
    - client（默认）：主动连接鹊桥的 WebSocket Server（正向）
    - server：本端作为 WebSocket Server，等待鹊桥 Client 连入（反向）
    """

    FATAL_CLOSE_CODES = {1008, 1003, 1010}
    FATAL_STATUS_CODES = {401, 403, 404}

    def __init__(
        self,
        ws_url: str = "ws://127.0.0.1:8080/minecraft/ws",
        headers: Optional[dict] = None,
        reconnect_interval: int = 10,
        max_retries: int = 5,
        mode: str = "client",
        server_host: str = "0.0.0.0",
        server_port: int = 8080,
        server_path: str = "/minecraft/ws",
        server_name: str = "Server",
        access_token: str = "",
        allow_replace_connection: bool = True,
        ping_interval: float = 30,
        ping_timeout: float = 10,
        alert_dispatcher: Optional[AlertDispatcher] = None,
    ):
        self.mode = (mode or "client").strip().lower()
        if self.mode not in ("client", "server"):
            logger.warning(f"未知 ws_mode={mode}，回退为 client")
            self.mode = "client"

        self.ws_url = ws_url
        self.headers = headers or {}
        self.reconnect_interval = reconnect_interval
        self.max_retries = max_retries

        self.server_host = server_host
        self.server_port = int(server_port)
        self.server_path = (
            server_path if server_path.startswith("/") else f"/{server_path}"
        )
        self.server_name = server_name
        self.access_token = access_token or ""
        self.allow_replace_connection = allow_replace_connection
        self.ping_interval = ping_interval
        self.ping_timeout = ping_timeout

        # 连接状态
        self.connected = False
        self.websocket = None
        self.should_reconnect = True
        self.total_retries = 0

        # server 模式内部状态
        self._shared_server: Optional[SharedReverseServer] = None
        self._client_gone = asyncio.Event()
        self._closed = asyncio.Event()
        self._send_lock = asyncio.Lock()
        self._stop_event = asyncio.Event()
        self._start_task: Optional[asyncio.Task] = None
        self._closing = False
        self.health = WebSocketWatchdog(self.server_name)
        self.alert_dispatcher = alert_dispatcher or AlertDispatcher()
        self.alert_results = deque(maxlen=32)
        self._alert_tasks = set()
        self._had_disconnect = False

        self.message_handler: Optional[Callable[[str], Awaitable[None]]] = None

        # 待响应的 API 请求：echo -> (api_name, Future)
        self._pending_api: Dict[str, Tuple[str, "asyncio.Future"]] = {}

        # One adapter owns one cache. Generation and epoch fence late replies.
        self.connection_generation = 0
        self._player_list_epoch = 0
        self.player_list_cache = PlayerListCache(default_ttl=5.0, max_capacity=16)
        self._player_list_flights: Dict[str, asyncio.Task] = {}

    def invalidate_player_list(self):
        """Invalidate a cached answer and fence every already-started fetch."""
        self._player_list_epoch += 1
        self.player_list_cache.clear()

    def _abort_api_waiters(self, reason: str):
        for _, future in self._pending_api.values():
            if not future.done():
                future.set_exception(ConnectionError(reason))
        self._pending_api.clear()

    def _queue_alert(self, title: str, severity: AlertSeverity,
                     cause: str, generation: int):
        alert = AlertPayload(
            server_name=self.server_name, severity=severity, title=title,
            message=cause, generation=generation,
        )
        async def deliver():
            result = await self.alert_dispatcher.dispatch(alert)
            self.alert_results.append(result)
            if result.status == "failed":
                logger.warning(f"[{self.server_name}] 连接告警发送失败: {result.error}")
            elif result.status == "unconfigured":
                logger.info(f"[{self.server_name}] 连接状态变化，未配置告警发送器: {title}")

        task = asyncio.create_task(deliver())
        self._alert_tasks.add(task)
        task.add_done_callback(self._alert_tasks.discard)

    @staticmethod
    def _disconnect_cause(error) -> str:
        if error is None:
            return "transport_closed"
        if "keepalive ping timeout" in str(error).lower():
            return "keepalive_timeout"
        return f"transport_error:{type(error).__name__}"

    def _activate_connection(self, websocket):
        recovered = self._had_disconnect
        self.connection_generation += 1
        self.invalidate_player_list()
        self._abort_api_waiters("WebSocket connection replaced")
        self.websocket = websocket
        self.connected = True
        self.health.record_connected(self.connection_generation)
        self._had_disconnect = False
        if recovered and not self._closing:
            self._queue_alert("connection_recovered", AlertSeverity.INFO,
                              "transport_open", self.connection_generation)

    def _drop_connection(self, websocket=None, error=None, shutdown=False):
        if websocket is not None and websocket is not self.websocket:
            return
        if self.websocket is None and not self.connected:
            return
        generation = self.connection_generation
        cause = "shutdown" if shutdown else self._disconnect_cause(error)
        transition = self.health.record_disconnected(generation, cause)
        self.connection_generation += 1
        self.invalidate_player_list()
        self._abort_api_waiters("WebSocket disconnected")
        self.websocket = None
        self.connected = False
        if transition and not shutdown and not self._closing:
            self._had_disconnect = True
            self._queue_alert("connection_disconnected", AlertSeverity.WARN,
                              cause, generation)

    @staticmethod
    def _valid_player_list(response) -> bool:
        if not isinstance(response, dict) or response.get("status") != "ok":
            return False
        data = response.get("data")
        if not isinstance(data, dict):
            return False
        players = data.get("players")
        count = data.get("count")
        maximum = data.get("max_players")
        return (
            isinstance(players, list)
            and all(isinstance(player, dict) for player in players)
            and isinstance(count, int) and not isinstance(count, bool)
            and isinstance(maximum, int) and not isinstance(maximum, bool)
            and count == len(players) and 0 <= count <= maximum
        )

    async def query_player_list(self, fetch: Callable[[], Awaitable[dict]], config_key: str = ""):
        """Coalesce misses; cancellation of one caller leaves the fetch alive."""
        while True:
            generation = self.connection_generation
            epoch = self._player_list_epoch
            key = repr((generation, epoch, config_key))
            cached = self.player_list_cache.get(key)
            if cached is not None:
                return cached
            task = self._player_list_flights.get(key)
            if task is None:
                async def run_fetch():
                    try:
                        response = await fetch()
                        if (self.connection_generation, self._player_list_epoch) == (generation, epoch):
                            if self._valid_player_list(response):
                                self.player_list_cache.set(key, response)
                        return response
                    finally:
                        self._player_list_flights.pop(key, None)

                task = asyncio.create_task(run_fetch())
                self._player_list_flights[key] = task
                # A caller may be cancelled while the owned fetch finishes later.
                task.add_done_callback(
                    lambda done: None if done.cancelled() else done.exception()
                )
            try:
                response = await asyncio.shield(task)
            except Exception:
                if self._closing:
                    # A manager shutdown is cancellation of its coalesced
                    # caller, rather than a user-visible transport failure.
                    raise asyncio.CancelledError()
                if (self.connection_generation, self._player_list_epoch) != (generation, epoch):
                    if self.connected:
                        continue
                    raise ConnectionError("WebSocket disconnected")
                raise
            if (self.connection_generation, self._player_list_epoch) != (generation, epoch):
                if self.connected:
                    continue
                raise ConnectionError("WebSocket disconnected")
            return response

    def set_message_handler(self, handler: Callable[[str], Awaitable[None]]):
        """设置消息处理回调函数"""
        self.message_handler = handler

    # ------------------------------------------------------------------
    # API 请求-响应分发
    # ------------------------------------------------------------------
    def register_api_waiter(self, echo: str, api_name: str) -> "asyncio.Future":
        """登记一个等待中的 API 请求，返回用于接收响应的 Future。

        必须在 send_message 之前调用，否则服务端的快速响应会被漏掉。
        """
        future: asyncio.Future = asyncio.get_running_loop().create_future()
        # A shutdown can race cancellation of the task awaiting this Future.
        future.add_done_callback(
            lambda done: None if done.cancelled() else done.exception()
        )
        self._pending_api[echo] = (api_name, future)
        return future

    def cancel_api_waiter(self, echo: str):
        """移除等待者（超时或异常时清理，避免泄漏）"""
        entry = self._pending_api.pop(echo, None)
        if entry is not None and not entry[1].done():
            entry[1].cancel()

    def _resolve_api_response(self, message: str) -> bool:
        """尝试把消息投递给等待中的 API 请求。

        Returns:
            bool: True 表示该消息已被消费，不再交给普通消息处理器。
        """
        if not self._pending_api:
            return False

        try:
            data = json.loads(message)
        except Exception:
            return False

        if not isinstance(data, dict) or "status" not in data:
            return False

        echo = data.get("echo")
        entry = self._pending_api.get(echo) if echo else None

        # Only genuinely echo-less legacy replies may use the fallback.
        # An unknown echo must never consume a newer request after reconnect.
        if entry is None:
            if echo is not None:
                return False
            api_name = self._guess_api_name(data)
            if api_name is None:
                return False
            candidates = [
                (key, value)
                for key, value in self._pending_api.items()
                if value[0] == api_name
            ]
            if len(candidates) != 1:
                return False
            echo, entry = candidates[0]

        self._pending_api.pop(echo, None)
        _, future = entry
        if not future.done():
            future.set_result(data)
        return True

    @staticmethod
    def _guess_api_name(data: dict) -> Optional[str]:
        """从响应体反推它属于哪个 API（仅用于兼容无 echo 的旧版本）"""
        payload = data.get("data")
        if not isinstance(payload, dict):
            return None
        if payload.get("players") is not None:
            return "get_player_list"
        return None

    async def _dispatch_message(self, message: str, websocket=None):
        """接收循环统一入口：先给 API 等待者，其余交给普通处理器。"""
        if websocket is not None and websocket is not self.websocket:
            return
        if self._resolve_api_response(message):
            return
        if self.message_handler:
            await self.message_handler(message)

    def _is_fatal_error(self, error) -> bool:
        """判断是否为致命错误（不应重试）"""
        if isinstance(error, websockets.exceptions.ConnectionClosed):
            return error.code in self.FATAL_CLOSE_CODES
        # 兼容不同版本异常名
        invalid_status = getattr(websockets.exceptions, "InvalidStatusCode", None) or getattr(
            websockets.exceptions, "InvalidStatus", None
        )
        if invalid_status and isinstance(error, invalid_status):
            status = getattr(error, "status_code", None) or getattr(error, "status", None)
            return status in self.FATAL_STATUS_CODES
        return False

    async def start(self):
        """Start one owned transport loop; close() can wake and await it."""
        current = asyncio.current_task()
        if self._start_task is not None and self._start_task is not current:
            if not self._start_task.done():
                return
        self._start_task = current
        self._closing = False
        self.should_reconnect = True
        self._stop_event.clear()
        self._closed.clear()
        try:
            if self.mode == "server":
                await self._start_server_mode()
            else:
                await self._start_client_mode()
        finally:
            self._closed.set()
            if self._start_task is current:
                self._start_task = None

    async def _wait_retry(self, seconds: float):
        try:
            await asyncio.wait_for(self._stop_event.wait(), timeout=max(0, seconds))
        except asyncio.TimeoutError:
            pass

    async def _start_client_mode(self):
        """正向：作为 Client 连接鹊桥 Server。"""
        while self.should_reconnect:
            try:
                async with websockets.connect(
                    self.ws_url,
                    additional_headers=self.headers,
                    ping_interval=self.ping_interval,
                    ping_timeout=self.ping_timeout,
                    close_timeout=1,
                    proxy=None,
                ) as websocket:
                    if self._closing or not self.should_reconnect:
                        await websocket.close()
                        break
                    self._activate_connection(websocket)
                    self.total_retries = 0
                    logger.info(
                        f"成功连接到鹊桥模组 WebSocket 服务器: {self.ws_url}"
                    )

                    async for message in websocket:
                        logger.debug(f"原始 WebSocket 消息: {message}")
                        await self._dispatch_message(message, websocket)
                    self._drop_connection(websocket)

            except (
                websockets.exceptions.ConnectionClosed,
                websockets.exceptions.WebSocketException,
                ConnectionRefusedError,
                asyncio.TimeoutError,
                OSError,
            ) as e:
                self._drop_connection(error=e)

                if not self.should_reconnect:
                    break

                if self._is_fatal_error(e):
                    logger.error(f"致命错误，停止重试: {e}")
                    self.should_reconnect = False
                    break

                self.total_retries += 1
                if self.total_retries > self.max_retries:
                    logger.error(
                        f"WebSocket 连接失败次数已达到最大限制"
                        f"({self.max_retries}次)，停止重试"
                    )
                    self.should_reconnect = False
                    break

                wait_time = min(
                    self.reconnect_interval * self.total_retries, 60
                )
                logger.error(
                    f"WebSocket 连接错误: {e}, "
                    f"将在{wait_time}秒后尝试重新连接..."
                    f"(第{self.total_retries}次)"
                )
                await self._wait_retry(wait_time)

            except Exception as e:
                self._drop_connection(error=e)
                logger.error(f"WebSocket 处理未知错误: {e}")
                if not self.should_reconnect:
                    break
                await self._wait_retry(self.reconnect_interval)

        self._drop_connection()
        self._closed.set()

    async def _start_server_mode(self):
        """反向：作为 Server 等待鹊桥 Client 连入。"""
        with _SHARED_LOCK:
            key = (self.server_host, self.server_port)
            shared = _SHARED_SERVERS.get(key)
            if shared is None:
                shared = SharedReverseServer(
                    self.server_host, self.server_port, self.server_path,
                    self.ping_interval, self.ping_timeout,
                )
                _SHARED_SERVERS[key] = shared
            # 同端口 path 不一致时告警
            if shared.path != self.server_path:
                logger.warning(
                    f"反向 WS 端口 {self.server_port} 已使用 path="
                    f"{shared.path}，当前适配器 path={self.server_path} 将被忽略"
                )
            shared.register(self.server_name, self)
            self._shared_server = shared
            await shared.start()

        logger.info(
            f"适配器 {self.server_name} 进入反向模式，"
            f"等待鹊桥 Client 连接 "
            f"ws://{self.server_host}:{self.server_port}{shared.path}"
        )

        # 阻塞直到 close() 被调用
        try:
            await self._closed.wait()
        finally:
            await self._detach_from_shared_server()

    async def _on_server_client_connected(self, websocket):
        """server 模式：处理单个鹊桥 Client 连接生命周期。"""
        if self._closing or not self.should_reconnect:
            await websocket.close(1001, "Manager closing")
            return
        # Publish the new generation before closing the old transport.
        old = self.websocket
        self._activate_connection(websocket)
        if old is not None and old is not websocket:
            try:
                await old.close(1000, "Replaced by new connection")
            except Exception:
                pass
        self._client_gone.clear()
        logger.info(f"[{self.server_name}] 反向 WebSocket 已建立")

        disconnect_error = None
        try:
            async for message in websocket:
                logger.debug(
                    f"[{self.server_name}] 反向 WS 原始消息: {message}"
                )
                try:
                    await self._dispatch_message(message, websocket)
                except Exception as e:
                    logger.error(
                        f"[{self.server_name}] 处理反向 WS 消息出错: {e}"
                    )
        except websockets.exceptions.ConnectionClosed as e:
            disconnect_error = e
            logger.warning(
                f"[{self.server_name}] 反向 WS 连接关闭: code={e.code}, "
                f"reason={e.reason}"
            )
        except Exception as e:
            disconnect_error = e
            logger.error(f"[{self.server_name}] 反向 WS 连接异常: {e}")
        finally:
            self._drop_connection(websocket, error=disconnect_error)
            self._client_gone.set()
            logger.info(f"[{self.server_name}] 反向 WebSocket 已断开")

    async def _detach_from_shared_server(self):
        with _SHARED_LOCK:
            shared = self._shared_server
            if shared is None:
                return
            shared.unregister(self.server_name)
            key = (shared.host, shared.port)
            if shared.is_empty:
                await shared.stop()
                _SHARED_SERVERS.pop(key, None)
            self._shared_server = None

    async def send_message(self, message: dict) -> bool:
        """发送消息到 WebSocket。"""
        if not self.connected or not self.websocket:
            logger.error("无法发送消息：WebSocket 未连接")
            return False

        try:
            async with self._send_lock:
                await self.websocket.send(json.dumps(message, ensure_ascii=False))
            return True
        except Exception as e:
            logger.error(f"发送 WebSocket 消息时出错: {str(e)}")
            return False

    async def close(self):
        """关闭 WebSocket 连接 / 服务端。"""
        self._closing = True
        self.should_reconnect = False
        self._stop_event.set()

        ws = self.websocket
        self._drop_connection(shutdown=True)
        flights = list(self._player_list_flights.values())
        for task in flights:
            task.cancel()
        if flights:
            await asyncio.gather(*flights, return_exceptions=True)
        self._player_list_flights.clear()
        if ws is not None:
            try:
                await ws.close()
            except Exception:
                pass

        self._closed.set()

        if self.mode == "server":
            await self._detach_from_shared_server()

        alerts = list(self._alert_tasks)
        for task in alerts:
            task.cancel()
        if alerts:
            await asyncio.gather(*alerts, return_exceptions=True)
        self._alert_tasks.clear()

        start_task = self._start_task
        if start_task is not None and start_task is not asyncio.current_task():
            try:
                await asyncio.wait_for(asyncio.shield(start_task), timeout=5)
            except asyncio.TimeoutError:
                start_task.cancel()
                await asyncio.gather(start_task, return_exceptions=True)

        logger.info(
            f"WebSocket 已关闭 (mode={self.mode}, server_name={self.server_name})"
        )
