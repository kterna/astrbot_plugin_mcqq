# MCQQ 插件

一个通过鹊桥模组实现Minecraft平台适配器，以及mcqq互联的插件。
[![moe_counter](https://count.getloli.com/get/@astrbot_plugin_mcqq?theme=moebooru)](https://github.com/kterna/astrbot_plugin_mcqq)

## 功能

- 将 Minecraft 聊天消息转发到 QQ 群
- 将 QQ 群消息转发到 Minecraft 服务器
- 支持玩家加入/退出服务器的消息通知
- 在游戏内输入"#qq"开头的消息可自动转发到QQ群
- 在游戏内输入"#astr"开头的消息可调用astrbot框架的指令或llm

## 安装要求

- Minecraft 服务器安装鹊桥模组（queqiao）
https://www.curseforge.com/minecraft/mc-mods/queqiao

### 使用说明

在平台适配器中新增minecraft平台适配器，并配置相关配置连接到minecraft服务器
在服务器中可使用"#astr"命令进行astrbot自身的指令或llm
![llm](image/llm.png)
![help](image/help.png)

### 配置项说明

- `WEBSOCKET_URL`: 鹊桥模组的WebSocket服务器地址
- `SERVER_NAME`: 服务器名称，必须与鹊桥模组配置中的server_name一致
- `AUTHORIZATION`: 访问令牌，如果鹊桥模组配置了access_token则需要填写
- `QQ_MESSAGE_PREFIX`: 转发到QQ消息的前缀
- `ENABLE_JOIN_QUIT_MESSAGES`: 是否转发玩家加入/退出服务器的消息
- `MAX_RECONNECT_RETRIES`: 连接断开后最大重试次数，默认5次
- `RECONNECT_INTERVAL`: 重连间隔（秒），默认3秒
- `FILTER_BOTS`:是否开启假人消息筛选
- `BOT_PREFIX`:假人前缀
- `BOT_SUFFIX`:假人后缀

## 更新日志

- v1.3.1 修复bug，增加识别假人功能，若配置中未出现对应配置项请删除重新创建
- v1.3.0 增加了minecraft平台适配器，将minecraft服务器接入了astrbot框架
- v1.2.0 fix README
- v1.1.0 修复插件数据路径，增加多服务端的支持
- v1.0.0 发布测试版本

## TODO
支持更多minecraft服务器

## 注意事项

目前为测试性开发，未测试所有minecraft客户端，可能存在未知问题
在minecraft中使用astrbot命令无法支持图片、语音、视频等，目前仅支持文字
可以配置筛选假人消息不广播，假人通过前缀或后缀进行筛选

## 命令

qq命令:
- `mcsay <消息>`: 向Minecraft服务器发送消息
- `mcbind`：绑定群聊
- `mcunbind`：取消绑定
- `mcstatus`：查看服务器连接状态

mc命令:
- `#qq <消息>`:向qq群发送消息
- `#astr <消息>`:调用astrbot框架的指令或llm

## 鹊桥模组配置

确保Minecraft服务器已安装鹊桥模组（queqiao），并且config.yml配置如下：

```json
{
  "server_name": "Server",  // 必须与插件中的SERVER_NAME一致
  "access_token": "your_secure_token",  // 建议设置安全token并在插件配置中填写相同的值
  "websocket": {
    "host": "127.0.0.1",
    "port": 8080
  }
}
```