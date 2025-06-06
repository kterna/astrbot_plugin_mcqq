from abc import ABC, abstractmethod
from typing import List, Dict, Any, Optional
import asyncio

from astrbot.api.platform import Platform
from astrbot import logger


class BaseMinecraftAdapter(Platform, ABC):
    """Minecraft平台适配器基类"""
    
    def __init__(self, platform_config: dict, platform_settings: dict, event_queue: asyncio.Queue):
        super().__init__(event_queue)
        self.config = platform_config
        self.settings = platform_settings
        self.adapter_id = self.config.get("adapter_id", self.__class__.__name__)
        
    @abstractmethod
    async def is_connected(self) -> bool:
        """检查适配器是否已连接"""
        pass
        
    @property
    @abstractmethod
    def server_name(self) -> str:
        """获取服务器名称"""
        pass 