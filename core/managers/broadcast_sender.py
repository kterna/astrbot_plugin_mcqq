import asyncio
import datetime
from typing import List, Dict, Any
from astrbot import logger
from ..utils.message_builder import MessageBuilder


class BroadcastSender:
    """处理广播消息的发送"""

    def __init__(self, send_interval: float = 0.1):
        """
        初始化发送器。

        Args:
            send_interval (float, optional): 多个适配器之间的发送间隔. Defaults to 0.1.
        """
        self.send_interval = send_interval

    async def send_rich_broadcast(self, adapters: List[Any], components: List[Dict[str, Any]]) -> bool:
        """
        向所有绑定的群组发送富文本广播。

        Args:
            adapters (List[Any]): 适配器实例列表。
            components (List[Dict[str, Any]]): 消息组件列表。

        Returns:
            bool: 是否至少向一个适配器成功发送。
        """
        if not adapters:
            logger.warning("未提供任何适配器，无法发送广播")
            return False
            
        tasks = [self._send_separately(adapter, components) for adapter in adapters]
        results = await asyncio.gather(*tasks)
        
        return any(results)

    async def send_custom_rich_broadcast(self, adapters: List[Any], text_content: str, click_value: str, hover_text: str, click_action: str = "SUGGEST_COMMAND") -> bool:
        """
        发送自定义的富文本广播。

        Args:
            adapters (List[Any]): 适配器实例列表。
            text_content (str): 主要文本内容。
            click_value (str): 点击事件的值。
            hover_text (str): 悬浮事件的文本。
            click_action (str, optional): 点击事件的动作. Defaults to "SUGGEST_COMMAND".

        Returns:
            bool: 是否发送成功。
        """
        if not adapters:
            logger.warning("未找到任何适配器，无法发送自定义广播")
            return False
            
        message_builder = MessageBuilder()
        message_builder.add_component(text_content, click_action=click_action, click_value=click_value, hover_text=hover_text)
        components = message_builder.build()

        return await self.send_rich_broadcast(adapters, components)

    async def _send_separately(self, adapter, components: List[Dict[str, Any]]) -> bool:
        """每个组件单独发送一条消息"""
        success_count = 0
        total_components = len(components)
        
        # 逐个发送每个组件
        for i, component in enumerate(components):
            # 处理时间变量替换
            current_time = datetime.datetime.now().strftime("%H:%M")
            component = component.copy()  # 创建副本避免修改原始配置
            component["text"] = component["text"].format(time=current_time)
            
            # 清理组件
            component = MessageBuilder.clean_component(component)
            
            
            # 创建广播消息
            broadcast_msg = MessageBuilder.create_broadcast_message([component])
            
            # 记录日志
            MessageBuilder.log_message(broadcast_msg, f"第 {i+1}/{total_components} 条广播消息")

            try:
                # 发送单条消息
                success = await adapter.websocket_manager.send_message(broadcast_msg)
                if success:
                    success_count += 1
                
                # 如果不是最后一条消息，添加延迟避免发送过快
                if i < total_components - 1:
                    await asyncio.sleep(self.send_interval)
                    
            except Exception as send_error:
                logger.error(f"发送第 {i+1} 条广播消息失败: {send_error}")
                continue

        # 判断是否全部发送成功
        if success_count == total_components:
            logger.info(f"富文本广播发送成功：共发送 {success_count} 条消息")
            return True
        elif success_count > 0:
            logger.warning(f"富文本广播部分成功：{success_count}/{total_components} 条消息发送成功")
            return True
        else:
            logger.error("富文本广播发送失败：所有消息都发送失败")
            return False