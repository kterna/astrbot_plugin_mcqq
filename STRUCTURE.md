# 项目结构说明

## 目录结构

```
astrbot_plugin_mcqq/
├── main.py                          # 插件主入口，注册命令和初始化
├── core/                            # 核心功能模块
│   ├── __init__.py                  # 核心模块初始化
│   ├── adapters/                    # 平台适配器
│   │   ├── __init__.py
│   │   └── minecraft_adapter.py     # Minecraft平台适配器
│   ├── managers/                    # 管理器模块
│   │   ├── __init__.py
│   │   ├── broadcast_manager.py     # 广播管理器
│   │   ├── rcon_manager.py          # RCON连接管理器
│   │   ├── group_binding_manager.py # 群组绑定管理器
│   │   └── process_manager.py       # 进程管理器
│   ├── handlers/                    # 处理器模块
│   │   ├── __init__.py
│   │   ├── command_handler.py       # 命令处理器
│   │   └── message_handler.py       # 消息处理器
│   ├── utils/                       # 工具模块
│   │   ├── __init__.py
│   │   ├── wiki_utils.py           # Wiki查询工具
│   │   └── bot_filter.py           # 假人过滤器
│   ├── events/                      # 事件模块
│   │   ├── __init__.py
│   │   └── minecraft_event.py      # Minecraft事件定义
│   └── config/                      # 配置模块
│       ├── __init__.py
│       └── server_types.py         # 服务器类型定义
├── README.md                        # 项目说明文档
├── metadata.yaml                    # 插件元数据
├── requirements.txt                 # 依赖包列表
├── LICENSE                          # 许可证
└── image/                          # 图片资源
```

## 模块职责说明

### 1. 主入口 (`main.py`)
- 插件注册和初始化
- 命令路由和事件处理
- 各模块的协调和管理

### 2. 适配器模块 (`core/adapters/`)
- **minecraft_adapter.py**: Minecraft平台适配器，负责与鹊桥模组的WebSocket连接

### 3. 管理器模块 (`core/managers/`)
- **broadcast_manager.py**: 整点广播和自定义广播管理
- **rcon_manager.py**: RCON连接和命令执行管理
- **group_binding_manager.py**: QQ群与服务器绑定关系管理
- **process_manager.py**: 外部进程管理

### 4. 处理器模块 (`core/handlers/`)
- **command_handler.py**: 集中处理所有QQ命令逻辑
- **message_handler.py**: 处理Minecraft消息的转发和解析

### 5. 工具模块 (`core/utils/`)
- **wiki_utils.py**: Minecraft Wiki查询功能
- **bot_filter.py**: 假人玩家过滤功能

### 6. 事件模块 (`core/events/`)
- **minecraft_event.py**: Minecraft相关事件定义

### 7. 配置模块 (`core/config/`)
- **server_types.py**: 不同Minecraft服务器类型的配置定义