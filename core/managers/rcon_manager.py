from typing import Optional
import aiomcrcon
from astrbot import logger


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
    
    async def initialize(self, adapter):
        """从适配器配置初始化RCON客户端并尝试连接"""
        if not adapter:
            logger.warning("RCON初始化推迟：等待Minecraft平台适配器可用...")
            return

        # 从适配器的配置中获取RCON设置
        self.rcon_enabled = adapter.config.get("rcon_enabled", False)
        self.rcon_host = adapter.config.get("rcon_host", "localhost")
        self.rcon_port = adapter.config.get("rcon_port", 25575)
        self.rcon_password = adapter.config.get("rcon_password", "")

        if not self.rcon_enabled:
            logger.info("RCON功能未在适配器配置中启用，跳过RCON初始化。")
            return

        if not self.rcon_password:
            logger.error("RCON密码未在适配器配置中配置，无法初始化RCON连接。")
            return
        
        if not self.rcon_host:
            logger.error("RCON主机未在适配器配置中配置，无法初始化RCON连接。")
            return

        await self._connect()
    
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

    async def execute_command(self, command: str, sender_id: str, adapter=None) -> tuple[bool, str]:
        """
        执行RCON命令
        
        Args:
            command: 要执行的命令
            sender_id: 发送者ID
            adapter: 适配器实例（重启命令需要）
            
        Returns:
            tuple[bool, str]: (成功标志, 响应消息)
        """
        # 检查 RCON 是否启用
        if not self.rcon_enabled:
            logger.info(f"RCON: 用户 {sender_id} 尝试执行rcon指令，但RCON功能未启用。")
            return False, "❌ RCON 功能当前未启用。请联系管理员在插件配置中启用。"
        
        # 重新连接命令
        if command == "重启":
            await self.initialize(adapter)  # 传递适配器进行重新初始化
            return True, "🔄 正在尝试重新连接RCON服务器..."
        
        if not command:
            return False, "❓ 请提供要执行的RCON指令，例如：/rcon whitelist add 玩家名"
        
        if not self.rcon_client or not self.rcon_connected:
            logger.warning(f"RCON: 用户 {sender_id} 尝试执行指令 '{command}' 但RCON未连接。")
            return False, "❌ RCON未连接到Minecraft服务器。正在尝试连接..."
        
        logger.info(f"RCON: 管理员 {sender_id} 正在执行指令: '{command}'")
        
        try:
            response = await self.rcon_client.send_cmd(command)
            if response:
                actual_response = response[0]
            else:
                actual_response = "无响应消息"
            
            logger.info(f"RCON: 指令 '{command}' 响应: {actual_response}")
            return True, actual_response
            
        except aiomcrcon.ClientNotConnectedError:
            logger.error("RCON: 在发送指令时发现客户端未连接。")
            self.rcon_connected = False
            return False, "❌ RCON客户端未连接。请重试或检查连接。"
        except Exception as e:
            logger.error(f"RCON: 执行指令 '{command}' 时发生错误: {e}")
            return False, f"❌ 执行RCON指令时发生错误: {e}"
    
    def is_enabled(self) -> bool:
        """检查RCON是否启用"""
        return self.rcon_enabled
    
    def is_connected(self) -> bool:
        """检查RCON是否已连接"""
        return self.rcon_connected 