import asyncio
from typing import Optional, Tuple
import aiomcrcon
from astrbot import logger

from ..utils.minecraft_utils import strip_minecraft_formatting_codes


class RconManager:
    """RCON连接和命令管理器"""
    
    def __init__(self):
        # RCON 相关属性
        self.rcon_client: Optional[aiomcrcon.Client] = None
        self.rcon_enabled: bool = False
        self.rcon_host: Optional[str] = None
        self.rcon_port: Optional[int] = None
        self.rcon_password: Optional[str] = None
        self.rcon_connected: bool = False
    
    def _validate_config(self, adapter) -> Tuple[bool, str]:
        """验证RCON配置的有效性"""
        if not adapter:
            return False, "等待Minecraft平台适配器可用..."
        
        self.rcon_enabled = adapter.config.get("rcon_enabled", False)
        if not self.rcon_enabled:
            return False, "RCON功能未在适配器配置中启用，跳过RCON初始化。"
        
        self.rcon_password = adapter.config.get("rcon_password", "")
        if not self.rcon_password:
            return False, "RCON密码未在适配器配置中配置，无法初始化RCON连接。"
        
        self.rcon_host = adapter.config.get("rcon_host", "localhost")
        if not self.rcon_host:
            return False, "RCON主机未在适配器配置中配置，无法初始化RCON连接。"
        
        self.rcon_port = adapter.config.get("rcon_port", 25575)
        return True, ""
    
    async def initialize(self, adapter):
        """从适配器配置初始化RCON客户端并尝试连接"""
        is_valid, error_msg = self._validate_config(adapter)
        if not is_valid:
            logger.warning(f"RCON初始化推迟：{error_msg}")
            return

        await self._connect()
    
    async def reconnect(self, adapter) -> bool:
        """重新连接RCON服务器"""
        try:
            await self.close()
            await self.initialize(adapter)
            return self.rcon_connected
        except Exception as e:
            logger.error(f"RCON重连失败: {e}")
            return False
    
    async def _connect(self):
        """建立RCON连接"""
        self.rcon_client = aiomcrcon.Client(self.rcon_host, self.rcon_port, self.rcon_password)
        logger.info(f"RCON: 正在尝试连接到服务器 {self.rcon_host}:{self.rcon_port}...")
        
        try:
            await self.rcon_client.connect()
            self.rcon_connected = True
            logger.info(f"RCON: 成功连接到服务器 {self.rcon_host}:{self.rcon_port}")
        except aiomcrcon.IncorrectPasswordError:
            logger.error(f"RCON连接失败：密码不正确。主机: {self.rcon_host}:{self.rcon_port}")
            self.rcon_client = None
        except aiomcrcon.RCONConnectionError as e:
            logger.error(f"RCON连接错误：无法连接到服务器 {self.rcon_host}:{self.rcon_port}。错误: {e}")
            self.rcon_client = None
        except Exception as e:
            logger.error(f"初始化RCON时发生未知错误: {e}")
            self.rcon_client = None

    async def close(self):
        """关闭RCON连接"""
        if self.rcon_client and self.rcon_connected:
            logger.info(f"RCON: 正在关闭与服务器 {self.rcon_host}:{self.rcon_port} 的连接...")
            try:
                await self.rcon_client.close()
                logger.info(f"RCON: 连接已成功关闭 ({self.rcon_host}:{self.rcon_port})")
            except Exception as e:
                logger.error(f"关闭RCON连接时发生错误: {e}")
            finally:
                self.rcon_connected = False
                self.rcon_client = None

    def _check_rcon_availability(self, sender_id: str, adapter=None) -> Tuple[bool, str]:
        """检查RCON是否可用，并在未连接时尝试重连"""
        if not self.rcon_enabled:
            logger.info(f"RCON: 用户 {sender_id} 尝试执行rcon指令，但RCON功能未启用。")
            return False, "❌ RCON 功能当前未启用。请联系管理员在插件配置中启用。"
        
        if not self.rcon_client or not self.rcon_connected:
            logger.warning(f"RCON: 用户 {sender_id} 尝试执行指令但RCON未连接。正在尝试自动重连...")
            
            # 尝试自动重连
            reconnect_success = asyncio.run_coroutine_threadsafe(self.reconnect(adapter), asyncio.get_running_loop()).result()
            
            if reconnect_success:
                logger.info("RCON: 自动重连成功。")
                return True, ""
            else:
                logger.error("RCON: 自动重连失败。")
                return False, "❌ RCON未连接到Minecraft服务器，自动重连失败。请手动使用 'rcon 重启' 命令。"
        
        return True, ""

    async def _handle_command_execution(self, command: str) -> str:
        """处理命令执行逻辑"""
        try:
            response = await self.rcon_client.send_cmd(command)
            actual_response = response[0] if response else "无响应消息"
            cleaned_response = strip_minecraft_formatting_codes(actual_response)
            logger.info(f"RCON: 指令 '{command}' 响应: {cleaned_response}")
            return cleaned_response
            
        except aiomcrcon.ClientNotConnectedError:
            logger.error("RCON: 在发送指令时发现客户端未连接。")
            self.rcon_connected = False
            raise
        except Exception as e:
            logger.error(f"RCON: 执行指令 '{command}' 时发生错误: {e}")
            raise

    async def execute_command(self, command: str, sender_id: str, adapter=None) -> Tuple[bool, str]:
        """
        执行RCON命令
        
        Args:
            command: 要执行的命令
            sender_id: 发送者ID
            adapter: 适配器实例（重启命令需要）
            
        Returns:
            Tuple[bool, str]: (成功标志, 响应消息)
        """
        # 重新连接命令
        if command == "重启":
            logger.info(f"RCON: 用户 {sender_id} 正在尝试重启RCON连接...")
            reconnect_success = await self.reconnect(adapter)
            if reconnect_success:
                return True, "✅ RCON连接已成功重启。"
            else:
                return False, "❌ RCON连接重启失败。请检查服务器状态和配置。"
        
        if not command:
            return False, "❓ 请提供要执行的RCON指令，例如：/rcon whitelist add 玩家名"
        
        # 检查RCON可用性
        is_available, error_msg = self._check_rcon_availability(sender_id, adapter)
        if not is_available:
            return False, error_msg
        
        logger.info(f"RCON: 管理员 {sender_id} 正在执行指令: '{command}'")
        
        try:
            response = await self._handle_command_execution(command)
            return True, response
        except aiomcrcon.ClientNotConnectedError:
            return False, "❌ RCON客户端未连接。请重试或检查连接。"
        except Exception as e:
            return False, f"❌ 执行RCON指令时发生错误: {e}"
    
    def is_enabled(self) -> bool:
        """检查RCON是否启用"""
        return self.rcon_enabled
    
    def is_connected(self) -> bool:
        """检查RCON是否已连接"""
        return self.rcon_connected 