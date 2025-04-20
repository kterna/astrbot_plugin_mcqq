# MCQQ 插件

一个连接 Minecraft 服务器与 QQ 群聊的 AstrBot 插件，通过鹊桥模组实现消息互通。

## 功能

- 将 Minecraft 聊天消息转发到 QQ 群
- 将 QQ 群消息转发到 Minecraft 服务器
- 支持玩家加入/退出服务器的消息通知

## 安装要求

- Minecraft 服务器安装鹊桥模组（QuickBridge）

### 配置项说明

- `WEBSOCKET_URL`: 鹊桥模组的WebSocket服务器地址
- `SERVER_NAME`: 服务器名称，必须与鹊桥模组配置中的server_name一致
- `ACCESS_TOKEN`: 访问令牌，如果鹊桥模组配置了access_token则需要填写
- `QQ_MESSAGE_PREFIX`: 转发到QQ消息的前缀
- `ENABLE_JOIN_QUIT_MESSAGES`: 是否转发玩家加入/退出服务器的消息

## 命令

- `mcsay <消息>`: 向Minecraft服务器发送消息
- `mcbind <SERVER_NAME>`：绑定群聊到server
- `mcunbind <SERVER_NAME>`：取消绑定
- `mcstatus`：查看服务器连接状态

## 鹊桥模组配置

确保Minecraft服务器已安装鹊桥模组（QuickBridge），并且config.yml配置如下：

```json
{
  "server_name": "Server",  // 必须与插件中的SERVER_NAME一致
  "access_token": "",       // 如果设置了token，需要在插件中也配置相同的值
  "websocket": {
    "host": "0.0.0.0",
    "port": 8080
  }
}
```
