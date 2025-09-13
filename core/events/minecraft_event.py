from astrbot.api.event import AstrMessageEvent, MessageChain
from astrbot.api.platform import AstrBotMessage, PlatformMetadata
from astrbot.api.message_components import Plain, Image
from astrbot import logger
from typing import Callable, Optional, Awaitable, TYPE_CHECKING
from astrbot.core.star.star_tools import StarTools
import os, base64, uuid
from astrbot.core.platform.astr_message_event import AstrMessageEvent
from astrbot.core.platform.astrbot_message import AstrBotMessage
from astrbot.core.platform.platform_metadata import PlatformMetadata
from astrbot.core.platform.message_type import MessageType  # 导入 MessageType

if TYPE_CHECKING:
    from ..adapters.minecraft_adapter import MinecraftPlatformAdapter

class MinecraftMessageEvent(AstrMessageEvent):
    def __init__(
        self,
        message_str: str,
        message_obj: AstrBotMessage,
        platform_meta: PlatformMetadata,
        session_id: str,
        adapter: "MinecraftPlatformAdapter",
        message_type: MessageType = MessageType.GROUP_MESSAGE  # 添加 message_type 参数，并默认为群聊消息
    ):
        # 在调用父类构造函数之前，设置消息类型
        message_obj.type = message_type
        super().__init__(message_str, message_obj, platform_meta, session_id)
        self.adapter = adapter
        self.on_response: Optional[Callable[[str], Awaitable[None]]] = None

    async def send(self, message: MessageChain):
        """发送消息到Minecraft服务器"""
        try:
            # 提取消息文本
            message_text = ""
            ci_image_texts = []
            for item in message.chain:
                if isinstance(item, Plain):
                    message_text += item.text
                elif item.__class__.__name__ == "Image":
                    # 检查 file 字段是否为 base64 编码
                    file_field = getattr(item, 'file', '')
                    if isinstance(file_field, str) and file_field.startswith('base64://'):
                        base64_data = file_field[len('base64://'):]
                        image_bytes = base64.b64decode(base64_data)
                        temp_dir = StarTools.get_data_dir('mcqq//temp')
                        temp_dir.mkdir(parents=True, exist_ok=True)
                        file_path = temp_dir / f"{uuid.uuid4()}.jpg"
                        with open(file_path, 'wb') as f:
                            f.write(image_bytes)
                        ci_image_texts.append(f"[[CICode,url=file:///{file_path},name=Image]]")
                    elif isinstance(file_field, str) and file_field.startswith('file:///'):
                        ci_image_texts.append(f"[[CICode,url={file_field},name=Image]]")
                    elif hasattr(item, 'url') and item.url:
                        ci_image_texts.append(f"[[CICode,url={item.url},name=Image]]")

            # 将图片消息以指定格式追加到文本末尾
            if ci_image_texts:
                message_text = message_text.strip() + ' ' + ' '.join(ci_image_texts)

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
