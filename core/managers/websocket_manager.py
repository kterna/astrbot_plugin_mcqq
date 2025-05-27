import asyncio
import json
import websockets
from typing import Callable, Awaitable
from astrbot import logger


class WebSocketManager:
    """WebSocket连接管理器，负责与鹊桥模组的WebSocket连接"""
    
    def __init__(self, ws_url: str, headers: dict, reconnect_interval: int = 10, max_retries: int = 5):
        self.ws_url = ws_url
        self.headers = headers
        self.reconnect_interval = reconnect_interval
        self.max_retries = max_retries
        
        # 连接状态
        self.connected = False
        self.websocket = None
        self.should_reconnect = True
        self.total_retries = 0
        
        # 消息处理回调
        self.message_handler: Callable[[str], Awaitable[None]] = None
    
    def set_message_handler(self, handler: Callable[[str], Awaitable[None]]):
        """设置消息处理回调函数"""
        self.message_handler = handler
    
    async def start(self):
        """启动WebSocket客户端，维持连接"""
        retry_count = 0
        
        while self.should_reconnect:
            try:
                if not self.connected:
                    logger.info(f"正在连接到鹊桥模组WebSocket服务器: {self.ws_url}")
                    
                    # 记录token使用情况
                    if not self.headers.get("Authorization"):
                        logger.warning("未配置Authorization，连接可能不安全")

                    # 尝试建立连接
                    self.websocket = await websockets.connect(
                        self.ws_url,
                        additional_headers=self.headers,
                        ping_interval=30,  # 保持心跳
                        ping_timeout=10
                    )

                    self.connected = True
                    retry_count = 0  # 重置重试计数
                    self.total_retries = 0  # 重置总重试次数
                    logger.info("成功连接到鹊桥模组WebSocket服务器")

                    # 持续接收消息
                    while True:
                        try:
                            message = await self.websocket.recv()
                            logger.debug(f"原始WebSocket消息: {message}")
                            if self.message_handler:
                                await self.message_handler(message)
                        except websockets.exceptions.ConnectionClosed as e:
                            logger.warning(f"WebSocket连接已关闭，代码: {e.code}, 原因: {e.reason}")
                            self.connected = False
                            self.websocket = None
                            
                            # 检查是否是认证错误或其他永久性错误
                            if e.code == 1008:  # 策略违反（可能是认证失败）
                                logger.error(f"WebSocket连接因策略违反而关闭，可能是Authorization错误: {e.reason}")
                                self.should_reconnect = False
                                break
                            elif e.code == 1003:  # 不支持的数据
                                logger.error(f"WebSocket连接因不支持的数据而关闭: {e.reason}")
                                self.should_reconnect = False
                                break
                            elif e.code == 1010:  # 必需的扩展
                                logger.error(f"WebSocket连接因扩展问题而关闭: {e.reason}")
                                self.should_reconnect = False
                                break
                            
                            break

            except (websockets.exceptions.ConnectionClosed,
                    websockets.exceptions.WebSocketException,
                    ConnectionRefusedError,
                    asyncio.TimeoutError) as e:
                self.connected = False
                self.websocket = None
                
                # 检查是否是可能无法恢复的错误
                if isinstance(e, websockets.exceptions.InvalidStatusCode):
                    if e.status_code == 401:  # 未授权，可能是token错误
                        logger.error(f"WebSocket连接未授权(401)，请检查Authorization是否正确。停止重试。")
                        self.should_reconnect = False
                        break
                    elif e.status_code == 403:  # 禁止访问
                        logger.error(f"WebSocket连接被拒绝(403)，服务器拒绝访问。停止重试。")
                        self.should_reconnect = False
                        break
                    elif e.status_code == 404:  # 路径不存在
                        logger.error(f"WebSocket连接失败(404)，请检查ws_url是否正确。停止重试。")
                        self.should_reconnect = False
                        break

                retry_count += 1
                self.total_retries += 1
                wait_time = min(self.reconnect_interval * retry_count, 60)  # 指数退避，最大60秒

                if self.total_retries >= self.max_retries:
                    logger.error(f"WebSocket连接失败次数已达到最大限制({self.max_retries}次)，停止重试")
                    self.should_reconnect = False
                    break
                elif retry_count > self.max_retries:
                    logger.error(f"WebSocket连接失败次数过多({retry_count}次)，将在60秒后重试")
                    await asyncio.sleep(60)
                    retry_count = 0
                else:
                    logger.error(f"WebSocket连接错误: {e}, 将在{wait_time}秒后尝试重新连接...(第{retry_count}次，总计{self.total_retries}次)")
                    await asyncio.sleep(wait_time)

            except Exception as e:
                logger.error(f"WebSocket处理未知错误: {e}")
                await asyncio.sleep(self.reconnect_interval)
    
    async def send_message(self, message: dict) -> bool:
        """发送消息到WebSocket"""
        if not self.connected or not self.websocket:
            logger.error("无法发送消息：WebSocket未连接")
            return False

        try:
            await self.websocket.send(json.dumps(message))
            return True
        except Exception as e:
            logger.error(f"发送WebSocket消息时出错: {str(e)}")
            return False
    
    async def close(self):
        """关闭WebSocket连接"""
        self.should_reconnect = False
        if self.websocket:
            await self.websocket.close()
        logger.info("WebSocket连接已关闭") 