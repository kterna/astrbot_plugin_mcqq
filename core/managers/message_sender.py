import asyncio
from typing import List, Dict, Any
from astrbot import logger
from ..utils.message_builder import MessageBuilder


class MessageSender:
    """消息发送管理器，负责向Minecraft服务器发送各种类型的消息"""
    
    def __init__(self, websocket_manager):
        self.websocket_manager = websocket_manager
    
    async def send_broadcast_message(self, message: str, sender: str = None) -> bool:
        """发送广播消息到Minecraft服务器"""
        try:
            # 使用MessageBuilder创建简单广播消息
            broadcast_msg = MessageBuilder.create_simple_broadcast(message, sender)
            
            # 记录日志
            MessageBuilder.log_message(broadcast_msg, "广播消息")
            
            # 发送消息
            return await self.websocket_manager.send_message(broadcast_msg)

        except Exception as e:
            logger.error(f"发送广播消息到Minecraft时出错: {str(e)}")
            return False

    async def send_rich_message(self, text: str, click_url: str, hover_text: str, images: List[str], color: str = "#E6E6FA") -> bool:
        """发送富文本消息到Minecraft服务器"""
        try:
            # 使用MessageBuilder创建富文本广播消息
            broadcast_msg = MessageBuilder.create_rich_broadcast(
                text=text,
                color=color,
                click_url=click_url,
                hover_text=hover_text,
                images=images,
                click_action="OPEN_URL"
            )
            
            # 发送消息
            return await self.websocket_manager.send_message(broadcast_msg)

        except Exception as e:
            logger.error(f"发送富文本消息到Minecraft时出错: {str(e)}")
            return False
    
    async def send_private_message(self, uuid: str, components: List[Dict[str, Any]]) -> bool:
        """发送私聊消息到指定玩家"""
        try:
            success_count = 0
            total_components = len(components)
            
            # 逐个发送每个组件
            for i, component in enumerate(components):
                
                # 清理组件，移除None值
                component = MessageBuilder.clean_component(component)
                
                # 创建私聊消息
                private_msg = MessageBuilder.create_private_message(uuid, component)
                
                # 记录日志
                MessageBuilder.log_message(private_msg, f"第 {i+1}/{total_components} 条私聊消息")

                try:
                    # 发送单条私聊消息
                    success = await self.websocket_manager.send_message(private_msg)
                    if success:
                        success_count += 1
                    
                    # 如果不是最后一条消息，添加延迟避免发送过快
                    if i < total_components - 1:
                        await asyncio.sleep(0.1)  # 100ms延迟
                        
                except Exception as send_error:
                    logger.error(f"发送第 {i+1} 条私聊消息失败: {send_error}")
                    continue

            # 判断是否全部发送成功
            if success_count == total_components:
                logger.info(f"私聊消息发送成功：共发送 {success_count} 条消息")
                return True
            elif success_count > 0:
                logger.warning(f"私聊消息部分成功：{success_count}/{total_components} 条消息发送成功")
                return True
            else:
                logger.error("私聊消息发送失败：所有消息都发送失败")
                return False

        except Exception as e:
            logger.error(f"发送私聊消息到Minecraft时出错: {str(e)}")
            return False 