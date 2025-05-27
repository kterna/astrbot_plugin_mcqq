"""
自定义指令示例
展示如何使用装饰器系统注册新的Minecraft指令
"""

from typing import Dict, Any
from astrbot import logger
from ..core.handlers.message_handler import CommandHandler


class CustomCommandHandler(CommandHandler):
    """自定义指令处理器示例"""
    
    def __init__(self, message_handler):
        super().__init__(message_handler)
        self.priority = 50  # 中等优先级
    
    async def handle(self, 
                    message_text: str,
                    data: Dict[str, Any],
                    server_class,
                    bound_groups,
                    send_to_groups_callback,
                    send_mc_message_callback,
                    commit_event_callback,
                    platform_meta,
                    adapter=None) -> bool:
        """处理自定义指令"""
        
        # 示例：处理 #时间 指令
        if message_text.startswith("#时间"):
            import datetime
            current_time = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            await send_mc_message_callback(f"当前时间: {current_time}")
            return True
            
        # 示例：处理 #在线 指令
        elif message_text.startswith("#在线"):
            # 这里可以获取在线玩家列表
            player_data = data.get("player", {})
            player_name = player_data.get("nickname", "未知玩家")
            await send_mc_message_callback(f"你好 {player_name}！当前有N个玩家在线")
            return True
            
        return False


def register_custom_commands(message_handler):
    """
    注册自定义指令到消息处理器
    
    使用示例：
    from .examples.custom_commands import register_custom_commands
    register_custom_commands(message_handler)
    """
    
    # 方式1: 使用类注册
    custom_handler = CustomCommandHandler(message_handler)
    message_handler.register_command_handler(custom_handler)
    
    # 方式2: 使用装饰器注册
    @message_handler.command_handler(prefix="天气", priority=80)
    async def handle_weather_command(message_text: str, data: Dict[str, Any], **kwargs):
        """处理天气查询指令"""
        city = message_text[3:].strip()  # 去掉 #天气
        send_mc_message_callback = kwargs.get('send_mc_message_callback')
        
        if not city:
            await send_mc_message_callback("请指定城市名称，例如: #天气 北京")
        else:
            # 这里可以调用天气API
            await send_mc_message_callback(f"{city}的天气信息：晴天，25°C")
        return True
    
    @message_handler.command_handler(prefix="随机数", priority=60)
    async def handle_random_command(message_text: str, data: Dict[str, Any], **kwargs):
        """处理随机数生成指令"""
        import random
        send_mc_message_callback = kwargs.get('send_mc_message_callback')
        
        random_number = random.randint(1, 100)
        await send_mc_message_callback(f"随机数: {random_number}")
        return True
    
    @message_handler.command_handler(prefix="服务器", exact_match=True, priority=70)
    async def handle_server_info(message_text: str, data: Dict[str, Any], **kwargs):
        """处理服务器信息查询指令"""
        send_mc_message_callback = kwargs.get('send_mc_message_callback')
        
        server_info = """服务器信息:
版本: 1.20.1
在线玩家: 10/100
运行时间: 3天2小时"""
        await send_mc_message_callback(server_info)
        return True
    
    logger.info("自定义指令已注册完成") 