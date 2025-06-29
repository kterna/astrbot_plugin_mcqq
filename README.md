# MCQQ 插件

一个通过[鹊桥模组](https://www.curseforge.com/minecraft/mc-mods/queqiao)实现 Minecraft 平台适配器，并提供 QQ <-> MC 消息互通的 AstrBot 插件。

[![moe_counter](https://count.getloli.com/get/@astrbot_plugin_mcqq?theme=moebooru)](https://github.com/kterna/astrbot_plugin_mcqq)

[![Ask DeepWiki](https://deepwiki.com/badge.svg)](https://deepwiki.com/kterna/astrbot_plugin_mcqq)

## 核心功能

- **多服务器互通**: 将多个 MC 服务器连接在一起，实现跨服聊天、玩家事件（加入/退出/死亡）同步。
- **MC -> QQ**:
  - 玩家**加入/退出/死亡**事件转发到绑定的 QQ 群。
  - 在游戏内使用 `#qq <消息>` 将消息发送到 QQ 群。
  - 在游戏内使用 `#<指令>` 调用 AstrBot 的各项功能（包括 AI 对话）。
- **QQ -> MC**:
  - 将绑定的 QQ 群消息转发到 MC 服务器。
  - 使用 `/mcsay <消息>` 向所有连接的服务器发送广播。
  - 提供丰富的管理命令（RCON, 广播, 绑定等）。
- **高度可配置**: 支持假人过滤、自定义消息前缀、丰富的广播设置等。

---

## 目录

- [重要注意事项](#重要注意事项)
- [安装与配置](#安装与配置)
- [命令列表](#命令列表)
- [常见问题 (FAQ)](#常见问题-faq)
- [更新日志](#更新日志)

---

## 重要注意事项

- **聊天转发**: 默认情况下，只有以 `#` 开头的 MC 消息才会被插件处理。普通聊天消息**不会**被转发到 QQ 群。详见 [FAQ](#为什么我在-mc-里的聊天没有被转发到-qq)。
- **RCON 限制**: RCON 功能目前仅对**第一个**配置的服务器适配器生效。
- **配置重载**: 修改 `config.yaml` 中的 RCON 配置后，需要**完全重启 AstrBot** 才能生效。使用 `/rcon 重启` 命令仅会尝试重新连接，不会加载新配置。
- **版本更新**: 插件更新后，若适配器配置页面未出现新增的配置项，请**删除旧的适配器并重新创建**。
- **互通前提**: 多服务器互通功能需要所有服务器都安装[鹊桥模组](https://www.curseforge.com/minecraft/mc-mods/queqiao)或其 MCDR 移植版。
- **MCDR 特有功能**: `/mc玩家列表` 等部分高级功能仅在使用[鹊桥的 MCDR 移植版](https://github.com/kterna/queqiao_mcdr)时可用。

## 安装与配置

### 1. 环境要求

- **AstrBot**: 已安装并运行 AstrBot 框架。
- **Minecraft 服务器**:
  - 安装[鹊桥模组 (Queqiao)](https://www.curseforge.com/minecraft/mc-mods/queqiao)
  - 或安装[鹊桥的 MCDR 移植版](https://github.com/kterna/queqiao_mcdr)

### 2. 插件安装

- 将 `astrbot_plugin_mcqq` 文件夹放置到 AstrBot 的 `data/plugins` 目录下。
- 在 Astrbot 的插件市场中安装。

### 3. 鹊桥模组配置

确保鹊桥模组的 `config.yml` (或 MCDR 的 `config.py`) 配置正确，插件需要读取其中的信息。

**示例 `config.yml`:**
```yaml
server_name: "MyServer-1"  # 必须与插件适配器配置中的 SERVER_NAME 一致
access_token: "your_secure_token" # 建议设置, 并填入插件配置的 AUTHORIZATION
websocket:
  host: "127.0.0.1"
  port: 8080
```

### 4. 适配器配置

1.  在 AstrBot 的 **平台适配器** 设置中，新增 **Minecraft服务器适配器**。
2.  填写以下配置项：

- `adapter_id`: 适配器的唯一标识，例如 `mc_server_1`。
- `ws_url`: 鹊桥模组的 WebSocket 地址，例如 `ws://127.0.0.1:8080/minecraft/ws`。
- `server_name`: 服务器名称，**必须**与鹊桥模组配置中的 `server_name` 完全一致。
- `Authorization`: 访问令牌，如果鹊桥配置了 `access_token` 则必须填写。
- `enable_join_quit_messages`: (true/false) 是否转发玩家加入/退出消息。
- `qq_message_prefix`: 转发到 QQ 消息的前缀，例如 `[MC] `。
- `max_reconnect_retries`: 连接断开后最大重试次数（默认 5）。
- `reconnect_interval`: 重连间隔秒数（默认 3）。
- `filter_bots`: (true/false) 是否开启假人消息过滤。
- `bot_prefix`: 假人名称前缀列表，例如 `["bot_", "robot-"]`。
- `bot_suffix`: 假人名称后缀列表。
- `rcon_enabled`: (true/false) 是否启用 RCON 功能。
- `rcon_host`: RCON 地址。
- `rcon_port`: RCON 端口。
- `rcon_password`: RCON 密码 (必填)。

### 5. 绑定群聊

在需要接收 MC 消息的 QQ 群内，发送 `/mcbind` 命令，将该群与主服务器绑定。

---

## 命令列表

### QQ 群命令

- `/mcbind [服务器ID]`
  - **功能**: 绑定当前群聊与指定 MC 服务器。不指定服务器ID则绑定到主服务器。
  - **权限**: 管理员

- `/mcunbind [服务器ID]`
  - **功能**: 解除当前群聊与指定 MC 服务器的绑定。
  - **权限**: 管理员

- `/mcstatus`
  - **功能**: 查看所有 MC 适配器的连接状态和当前群聊的绑定信息。

- `/mcsay <消息>`
  - **功能**: 向所有已连接的 MC 服务器发送消息（支持图片）。

- `/rcon <指令>`
  - **功能**: 通过 RCON 在**主服务器**上执行指令。
  - **权限**: 管理员

- `/rcon 重启`
  - **功能**: 尝试重新连接**主服务器**的 RCON 服务。
  - **权限**: 管理员

- `/mc广播设置 <适配器ID> <配置>`
  - **功能**: 为指定服务器设置整点广播内容（支持富文本）。
  - **权限**: 管理员

- `/mc广播开关`
  - **功能**: 全局开启或关闭所有服务器的整点广播。
  - **权限**: 管理员

- `/mc广播测试`
  - **功能**: 立即触发一次整点广播进行测试。
  - **权限**: 管理员

- `/mc自定义广播 <文本>|<点击命令>|<悬浮文本>`
  - **功能**: 向所有服务器发送自定义的富文本广播。
  - **权限**: 管理员

- `/mc帮助`
  - **功能**: 显示本帮助信息。

- `/mc玩家列表`
  - **功能**: 获取服务器在线玩家列表。
  - **注意**: 此功能仅在使用[鹊桥的 MCDR 移植版](https://github.com/kterna/queqiao_mcdr)时可用，原版鹊桥模组不支持此API。

### Minecraft 游戏内命令

- `#qq <消息>`
  - **功能**: 将消息发送到所有绑定的 QQ 群。

- `#<指令>`
  - **功能**: 调用 AstrBot 的核心功能，例如 `#天气 北京` 或直接 `#你好` 与 AI 对话。

- `#wiki <词条>`
  - **功能**: 查询 Minecraft Wiki。

---

## 常见问题 (FAQ)

**Q: 为什么我在 MC 里的聊天没有被转发到 QQ？**
**A:** 这是设计使然。为了避免大量普通聊天刷屏，插件默认只处理和转发以 `#` 开头的消息。

**Q: 为什么 `/rcon` 命令没反应或提示失败？**
**A:** 请检查以下几点：
  1.  你是否是 AstrBot 管理员。
  2.  主服务器（第一个适配器）的 RCON 配置是否已启用并正确填写。
  3.  MC 服务器的 `server.properties` 文件中是否已启用 RCON。
  4.  服务器防火墙是否已放行 RCON 端口。
  5.  该功能目前只对第一个配置的服务器生效。

**Q: 连接状态显示"未连接"怎么办？**
**A:** 请检查：
  1.  MC 服务器及鹊桥模组是否正在运行。
  2.  插件适配器配置中的 `ws_url`, `server_name`, `Authorization` 是否与鹊桥的配置完全一致。
  3.  服务器防火墙是否已放行 WebSocket 端口。
  4.  尝试在 QQ 使用 `/mcstatus` 命令，它会自动触发一次重连。

**Q: `/mc玩家列表` 命令提示"请求失败"或没有响应？**
**A:** 请检查以下几点：
  1.  确保你使用的是[鹊桥的 MCDR 移植版](https://github.com/kterna/queqiao_mcdr)，原版鹊桥模组不支持此API。
  2.  MCDR 移植版是否已正确加载并运行。
  3.  服务器连接状态是否正常（可通过 `/mcstatus` 查看）。
  4.  MCDR 插件配置是否正确。

---

## 更新日志

- **v1.7.1**: 增加mcdr特定指令，修改readme。
- **v1.7.0**: 增加了对 MCDR 的支持。
- **v1.6.2**: 重构了部分代码。
- **v1.6.1**: 增加多服务器分别设置广播内容功能，修改广播数据结构。
- **v1.6.0**: 增加多服务器互通功能。
- **v1.5.1**: 修复bug，注册命令更简单、可维护。
- **v1.5.0**: 增加wiki查询，增加整点广播支持富文本内容。
- **v1.4.0**: 增加rcon命令。
- **v1.3.0**: 增加了minecraft平台适配器。
- **v1.0.0**: 发布测试版本。

## 许可证

本项目采用 MIT 许可证。