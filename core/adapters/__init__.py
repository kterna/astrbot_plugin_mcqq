"""
平台适配器模块
"""

# 适配器模块
from .base_adapter import BaseMinecraftAdapter
try:
    from .minecraft_adapter import MinecraftPlatformAdapter
except ImportError:
    MinecraftPlatformAdapter = None

try:
    from .rcon_guard import RconSecurityGuard, TokenBucket, GuardResult
except ImportError:
    RconSecurityGuard = None
    TokenBucket = None
    GuardResult = None

__all__ = ['BaseMinecraftAdapter', 'MinecraftPlatformAdapter', 'RconSecurityGuard', 'TokenBucket', 'GuardResult'] 