"""命令处理器模块，集中管理所有命令的处理逻辑"""
import asyncio
from typing import Optional
from astrbot.api.event import AstrMessageEvent
from astrbot import logger


class CommandHandler:
    """命令处理器类，用于分离命令处理逻辑"""
    
    def __init__(self, plugin_instance):
        self.plugin = plugin_instance
    
    async def handle_bind_command(self, event: AstrMessageEvent):
        """处理mcbind命令"""
        # 仅管理员可以使用此命令
        if not event.is_admin():
            return "⛔ 只有管理员才能使用此命令"

        group_id = event.get_group_id()
        if not group_id:
            return "❌ 此命令只能在群聊中使用"

        # 获取Minecraft适配器
        adapter = await self.plugin.get_minecraft_adapter()
        if not adapter:
            return "❌ 未找到Minecraft平台适配器，请确保适配器已正确注册并启用"

        # 绑定群聊
        success = await adapter.bind_group(group_id)
        if success:
            logger.info(f"群聊 {group_id} 与服务器 {adapter.server_name} 绑定")
            return "✅ 成功将本群与Minecraft服务器绑定"
        else:
            return "ℹ️ 此群已经与Minecraft服务器绑定"
    
    async def handle_unbind_command(self, event: AstrMessageEvent):
        """处理mcunbind命令"""
        # 仅管理员可以使用此命令
        if not event.is_admin():
            return "⛔ 只有管理员才能使用此命令"

        group_id = event.get_group_id()
        if not group_id:
            return "❌ 此命令只能在群聊中使用"

        # 获取Minecraft适配器
        adapter = await self.plugin.get_minecraft_adapter()
        if not adapter:
            return "❌ 未找到Minecraft平台适配器，请确保适配器已正确注册并启用"

        # 解除绑定
        success = await adapter.unbind_group(group_id)
        if success:
            logger.info(f"解除群聊 {group_id} 与服务器 {adapter.server_name} 的绑定")
            return "✅ 成功解除本群与Minecraft服务器的绑定"
        else:
            return "ℹ️ 此群未与Minecraft服务器绑定"
    
    async def handle_status_command(self, event: AstrMessageEvent):
        """处理mcstatus命令"""
        group_id = event.get_group_id()
        
        # 获取Minecraft适配器
        adapter = await self.plugin.get_minecraft_adapter()
        if not adapter:
            return "❌ 未找到Minecraft平台适配器，请确保适配器已正确注册并启用"

        # 如果未连接，尝试手动启动连接
        if not adapter.connected:
            # 通过websocket_manager正确重置连接状态
            adapter.websocket_manager.connected = False
            adapter.websocket_manager.websocket = None
            adapter.websocket_manager.should_reconnect = True
            adapter.websocket_manager.total_retries = 0
            
            # 启动新的重连任务
            asyncio.create_task(adapter.websocket_manager.start())
            return "⏳ Minecraft服务器未连接，正在尝试连接..."
        
        # 生成状态消息
        status_msg = f"🔌 Minecraft服务器连接状态: {'已连接' if adapter.connected else '未连接'}\n"
        
        # 添加绑定信息
        is_bound = adapter.is_group_bound(group_id)
        if is_bound:
            status_msg += "🔗 本群已绑定Minecraft服务器"
        else:
            status_msg += "🔗 本群未绑定Minecraft服务器"
        
        return status_msg
    
    async def handle_say_command(self, event: AstrMessageEvent):
        """处理mcsay命令"""
        message = event.message_str
        message = message.replace("mcsay", "", 1).strip()
        if not message:
            return "❓ 请提供要发送的消息内容，例如：/mcsay 大家好"

        # 获取Minecraft适配器
        adapter = await self.plugin.get_minecraft_adapter()
        if not adapter:
            return "❌ 未找到Minecraft平台适配器，请确保适配器已正确注册并启用"

        if not adapter.connected:
            return "❌ 未连接到Minecraft服务器，请检查连接"

        # 获取发送者信息
        sender_name = event.get_sender_name()

        # 发送消息到Minecraft
        await adapter.send_mc_message(message, sender_name)
        return f"✅ 消息已发送到Minecraft服务器"
    
    def handle_help_command(self, event: AstrMessageEvent):
        """处理mc帮助命令"""
        help_msg = """
Minecraft相关指令菜单:
qq群:
    '/'或@机器人可发起ai对话
    /mcbind - 绑定当前群聊与Minecraft服务器
    /mcunbind - 解除当前群聊与Minecraft服务器的绑定
    /mcstatus - 显示当前Minecraft服务器连接状态和绑定信息
    /mcsay - 向Minecraft服务器发送消息
    /rcon <指令> - 通过RCON执行Minecraft服务器指令 (仅管理员)
    /rcon 重启 - 尝试重新连接RCON服务器
    /mc广播设置 [富文本配置] - 设置整点广播富文本内容 (仅管理员)
    /mc广播开关 - 开启/关闭整点广播 (仅管理员)
    /mc广播测试 - 测试发送整点广播 (仅管理员)
    /mc广播清除 - 清除自定义广播内容，恢复默认 (仅管理员)
    /mc自定义广播 [文本]|[点击命令]|[悬浮文本] - 发送自定义富文本广播 (仅管理员)
    /投影 - 获取投影菜单帮助(依赖插件astrbot_plugin_litematic)
mc:
    #astr - 发起ai对话
    #qq - 向qq群发送消息
    #wiki 词条名称 - 查询Minecraft Wiki
    #重启qq - 若qq机器人无反应大概率是被腾讯踢掉了请输入这个命令
"""
        return help_msg
    
    async def handle_rcon_command(self, event: AstrMessageEvent):
        """处理rcon命令"""
        if not event.is_admin():
            return "⛔ 只有管理员才能使用此命令。"

        command_to_execute = event.message_str.replace("rcon", "", 1).strip()

        # 获取适配器（所有RCON操作都需要）
        adapter = await self.plugin.get_minecraft_adapter()
        
        # 如果是重启命令，需要传递适配器引用
        if command_to_execute == "重启":
            await self.plugin.rcon_manager.initialize(adapter)
            return "🔄 正在尝试重新连接RCON服务器..."

        # 执行RCON命令
        success, message = await self.plugin.rcon_manager.execute_command(
            command_to_execute, event.get_sender_id(), adapter
        )
        return message
    
    async def handle_broadcast_config_command(self, event: AstrMessageEvent):
        """处理mc广播设置命令"""
        # 仅管理员可以使用此命令
        if not event.is_admin():
            return "⛔ 只有管理员才能使用此命令"

        # 手动解析命令参数
        command_content = event.message_str.replace("mc广播设置", "", 1).strip()
        
        if not command_content:
            # 显示当前配置
            return self.plugin.broadcast_manager.get_current_config_display()

        # 解析并设置新的广播内容
        success, message = self.plugin.broadcast_manager.set_broadcast_content(command_content)
        if success:
            logger.info(f"整点广播内容已更新")
        return message
    
    async def handle_broadcast_toggle_command(self, event: AstrMessageEvent):
        """处理mc广播开关命令"""
        # 仅管理员可以使用此命令
        if not event.is_admin():
            return "⛔ 只有管理员才能使用此命令"

        # 切换广播状态
        new_status, message = self.plugin.broadcast_manager.toggle_broadcast()
        logger.info(f"整点广播已{'开启' if new_status else '关闭'}")
        return message
    
    async def handle_broadcast_clear_command(self, event: AstrMessageEvent):
        """处理mc广播清除命令"""
        # 仅管理员可以使用此命令
        if not event.is_admin():
            return "⛔ 只有管理员才能使用此命令"

        # 清除自定义广播内容
        success, message = self.plugin.broadcast_manager.clear_custom_content()
        if success:
            logger.info("已清除自定义广播内容")
        return message
    
    async def handle_broadcast_test_command(self, event: AstrMessageEvent):
        """处理mc广播测试命令"""
        # 仅管理员可以使用此命令
        if not event.is_admin():
            return "⛔ 只有管理员才能使用此命令"

        # 调用整点广播执行方法
        await self.plugin.broadcast_manager.execute_hourly_broadcast(self.plugin._broadcast_callback)
        return "✅ 测试广播已执行完成"
    
    async def handle_custom_broadcast_command(self, event: AstrMessageEvent):
        """处理mc自定义广播命令"""
        # 仅管理员可以使用此命令
        if not event.is_admin():
            return "⛔ 只有管理员才能使用此命令"

        # 手动解析命令参数
        command_content = event.message_str.replace("mc自定义广播", "", 1).strip()
        
        if not command_content:
            return "❓ 使用方法: mc自定义广播 [文本]|[点击命令]|[悬浮文本]\n💡 示例: mc自定义广播 欢迎来到服务器！|/say test|点击发送测试"

        # 解析三个参数，用|分隔
        params = command_content.split("|")
        
        if len(params) != 3:
            return "❌ 参数格式错误！\n🔧 正确格式: mc自定义广播 [文本]|[点击命令]|[悬浮文本]\n💡 示例: mc自定义广播 欢迎来到服务器！|/say test|点击发送测试"

        text_content = params[0].strip()
        click_value = params[1].strip()
        hover_text = params[2].strip()

        if not text_content:
            return "❌ 文本内容不能为空！"

        # 获取Minecraft适配器
        adapter = await self.plugin.get_minecraft_adapter()
        if not adapter:
            return "❌ 未找到Minecraft平台适配器，请确保适配器已正确注册并启用"

        if not adapter.connected:
            return "❌ 未连接到Minecraft服务器，请检查连接"

        # 发送自定义广播
        success = await self.plugin.broadcast_manager.send_custom_rich_broadcast(
            adapter, text_content, click_value, hover_text
        )
        
        if success:
            return f"✅ 自定义广播已发送\n📝 文本: {text_content}\n🖱️ 点击: {click_value}\n💬 悬浮: {hover_text}"
        else:
            return "❌ 发送自定义广播失败，请检查连接状态" 