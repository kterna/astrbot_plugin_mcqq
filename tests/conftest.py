"""测试前置：stub astrbot，避免依赖完整运行时。"""

from __future__ import annotations

import sys
import types
from pathlib import Path


def _ensure_astrbot_stub():
    if "astrbot" in sys.modules and hasattr(sys.modules["astrbot"], "logger"):
        # 可能是不完整 stub
        pass

    astrbot = types.ModuleType("astrbot")

    class _Logger:
        def info(self, *a, **k):
            pass

        def warning(self, *a, **k):
            pass

        def error(self, *a, **k):
            pass

        def debug(self, *a, **k):
            pass

    astrbot.logger = _Logger()
    sys.modules["astrbot"] = astrbot

    # 防止导入插件根 __init__ 时炸
    api = types.ModuleType("astrbot.api")
    platform = types.ModuleType("astrbot.api.platform")

    class Platform:  # minimal
        def __init__(self, *a, **k):
            pass

    platform.Platform = Platform
    platform.AstrBotMessage = object
    platform.MessageMember = object
    platform.PlatformMetadata = object
    platform.MessageType = object
    event = types.ModuleType("astrbot.api.event")
    event.AstrMessageEvent = object
    event.filter = types.SimpleNamespace()

    core = types.ModuleType("astrbot.core")
    star = types.ModuleType("astrbot.core.star")
    star_tools = types.ModuleType("astrbot.core.star.star_tools")

    class StarTools:  # minimal
        @staticmethod
        def get_data_dir(*a, **k):
            return Path("/tmp")

    star_tools.StarTools = StarTools

    sys.modules["astrbot.api"] = api
    sys.modules["astrbot.api.platform"] = platform
    sys.modules["astrbot.api.event"] = event
    sys.modules["astrbot.core"] = core
    sys.modules["astrbot.core.star"] = star
    sys.modules["astrbot.core.star.star_tools"] = star_tools
    astrbot.api = api
    api.platform = platform
    api.event = event
    astrbot.core = core
    core.star = star
    star.star_tools = star_tools


def _ensure_aiomcrcon_stub():
    """stub aiomcrcon，测试不依赖真实 RCON 库。"""
    if "aiomcrcon" in sys.modules:
        return

    mod = types.ModuleType("aiomcrcon")

    class RCONConnectionError(Exception):
        pass

    class IncorrectPasswordError(Exception):
        pass

    class ClientNotConnectedError(Exception):
        pass

    class Client:
        """默认可连通的假客户端；测试可按需替换 mod.Client。"""

        def __init__(self, host, port, password):
            self.host = host
            self.port = port
            self.password = password

        async def connect(self):
            return None

        async def close(self):
            return None

        async def send_cmd(self, command):
            return (f"executed: {command}", 0)

    mod.Client = Client
    mod.RCONConnectionError = RCONConnectionError
    mod.IncorrectPasswordError = IncorrectPasswordError
    mod.ClientNotConnectedError = ClientNotConnectedError
    sys.modules["aiomcrcon"] = mod


_ensure_astrbot_stub()
_ensure_aiomcrcon_stub()

# 把 core 所在目录加入 path（插件根）
ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
