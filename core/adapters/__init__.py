"""
平台适配器模块
"""

# 适配器模块
from .base_adapter import BaseMinecraftAdapter
from .minecraft_adapter import MinecraftPlatformAdapter

__all__ = ['BaseMinecraftAdapter', 'MinecraftPlatformAdapter'] 