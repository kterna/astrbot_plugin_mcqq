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
    sys.modules["astrbot.api"] = api
    sys.modules["astrbot.api.platform"] = platform
    astrbot.api = api


_ensure_astrbot_stub()

# 把 core 所在目录加入 path（插件根）
ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
