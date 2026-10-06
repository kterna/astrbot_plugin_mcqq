"""pytest 引导插件（由 pytest.ini 的 `-p tests_bootstrap` 在 conftest 之前加载）。

插件根 `__init__.py` 会拉起整个 AstrBot 运行时（astrbot.api / psutil / ...）。
pytest 收集 tests/ 时会把仓库根当成 Package 并导入它，在没有 AstrBot 的环境里
必然失败。这里预先往 sys.modules 塞一个同名空壳，import 直接命中缓存，
`__init__.py` 不会被执行；测试自行按需导入 `core.*` 子模块。
"""

import sys
import types
from pathlib import Path

ROOT = Path(__file__).resolve().parent

_PKG_NAME = ROOT.name
if _PKG_NAME not in sys.modules:
    _shell = types.ModuleType(_PKG_NAME)
    _shell.__path__ = [str(ROOT)]
    sys.modules[_PKG_NAME] = _shell

if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

# Standalone stub for astrbot modules so tests can import core.* freely
if "astrbot" not in sys.modules:
    astrbot = types.ModuleType("astrbot")
    api = types.ModuleType("astrbot.api")
    event = types.ModuleType("astrbot.api.event")
    all_module = types.ModuleType("astrbot.api.all")

    class MessageChain:
        pass

    event.MessageChain = MessageChain
    all_module.MessageChain = MessageChain
    api.event = event
    api.all = all_module
    astrbot.api = api

    class _Logger:
        def info(self, *a, **k): pass
        def warning(self, *a, **k): pass
        def error(self, *a, **k): pass
        def debug(self, *a, **k): pass

    astrbot.logger = _Logger()
    sys.modules["astrbot"] = astrbot
    sys.modules["astrbot.api"] = api
    sys.modules["astrbot.api.event"] = event
    sys.modules["astrbot.api.all"] = all_module
