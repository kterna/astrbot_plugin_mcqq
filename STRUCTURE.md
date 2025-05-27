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
│   │   ├── process_manager.py       # 进程管理器
│   │   ├── websocket_manager.py     # WebSocket连接管理器
│   │   └── message_sender.py        # 消息发送管理器
│   ├── handlers/                    # 处理器模块
│   │   ├── __init__.py
│   │   ├── command_handler.py       # 命令处理器
│   │   └── message_handler.py       # 消息处理器
│   ├── utils/                       # 工具模块
│   │   ├── __init__.py
│   │   ├── wiki_utils.py           # Wiki查询工具
│   │   ├── bot_filter.py           # 假人过滤器
│   │   └── message_builder.py      # 消息构建工具
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
- **minecraft_adapter.py**: Minecraft平台适配器，负责协调各个管理器和处理器

### 3. 管理器模块 (`core/managers/`)
- **broadcast_manager.py**: 整点广播和自定义广播管理
- **rcon_manager.py**: RCON连接和命令执行管理
- **group_binding_manager.py**: QQ群与服务器绑定关系管理
- **process_manager.py**: 外部进程管理
- **websocket_manager.py**: WebSocket连接管理，负责与鹊桥模组的连接维护
- **message_sender.py**: 消息发送管理，负责向Minecraft服务器发送各种类型的消息

### 4. 处理器模块 (`core/handlers/`)
- **command_handler.py**: 集中处理所有QQ命令逻辑
- **message_handler.py**: 处理Minecraft消息的转发和解析

### 5. 工具模块 (`core/utils/`)
- **wiki_utils.py**: Minecraft Wiki查询功能
- **bot_filter.py**: 假人玩家过滤功能
- **message_builder.py**: 消息构建工具，提供统一的JSON消息格式构建方法

### 6. 事件模块 (`core/events/`)
- **minecraft_event.py**: Minecraft相关事件定义

### 7. 配置模块 (`core/config/`)
- **server_types.py**: 不同Minecraft服务器类型的配置定义

## 架构设计说明

### 职责分离
- **MinecraftPlatformAdapter**: 作为主要的协调器，负责初始化各个管理器并协调它们之间的工作
- **WebSocketManager**: 专门负责WebSocket连接的建立、维护、重连逻辑和消息接收
- **MessageSender**: 专门负责向Minecraft服务器发送各种类型的消息（广播、富文本、私聊等）
- **MessageHandler**: 负责处理从Minecraft接收到的消息并转发到QQ群
- **GroupBindingManager**: 负责管理QQ群与Minecraft服务器的绑定关系
- **MessageBuilder**: 提供统一的消息构建工具，避免重复的JSON构造代码

### 模块间通信
- 适配器通过依赖注入的方式使用各个管理器
- WebSocketManager通过回调函数将接收到的消息传递给适配器
- MessageSender通过WebSocketManager发送消息到Minecraft服务器
- MessageBuilder为各个管理器提供统一的消息格式构建服务
- 各个管理器保持相对独立，便于测试和维护

### 代码复用和维护性
- **MessageBuilder**工具类统一了所有JSON消息的构建逻辑，消除了重复代码
- 提供了验证、清理和日志记录等通用功能
- 支持多种消息类型：简单广播、富文本广播、私聊消息、管理员公告等
- 便于扩展新的消息类型和格式