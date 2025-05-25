from astrbot.api.event import AstrMessageEvent, MessageChain
from astrbot.api.platform import AstrBotMessage, PlatformMetadata
from astrbot.api.message_components import Plain, Image
from astrbot import logger
from typing import Callable, Optional, Awaitable

class MinecraftMessageEvent(AstrMessageEvent):
    def __init__(
        self,
        message_str: str,
        message_obj: AstrBotMessage,
        platform_meta: PlatformMetadata,
        session_id: str,
        adapter: "MinecraftPlatformAdapter"
    ):
        super().__init__(message_str, message_obj, platform_meta, session_id)
        self.adapter = adapter
        self.on_response: Optional[Callable[[str], Awaitable[None]]] = None

    async def send(self, message: MessageChain):
        """发送消息到Minecraft服务器"""
        try:
            # 提取消息文本
            message_text = ""
            for item in message.chain:
                if isinstance(item, Plain):
                    message_text += item.text

            # 获取发送者信息
            sender_name = self.get_sender_name()

            # 如果有回调函数，使用回调函数发送消息
            if self.on_response:
                try:
                    await self.on_response(message_text)
                except Exception as e:
                    logger.error(f"调用响应回调时出错: {str(e)}")
                    # 如果回调失败，使用默认方式发送
                    await self.adapter.send_mc_message(message_text, sender_name)
            else:
                # 没有回调函数，直接发送消息到Minecraft
                await self.adapter.send_mc_message(message_text, sender_name)

            # 调用父类方法
            await super().send(message)
        except Exception as e:
            logger.error(f"发送消息到Minecraft时出错: {str(e)}")

    def get_group_id(self) -> str:
        """获取群聊ID"""
        return self.message_obj.group_id if hasattr(self.message_obj, "group_id") else None

    def is_group_bound(self) -> bool:
        """检查当前群聊是否与Minecraft服务器绑定"""
        group_id = self.get_group_id()
        if not group_id:
            return False
        return self.adapter.is_group_bound(group_id)
