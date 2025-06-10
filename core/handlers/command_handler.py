"""命令处理器模块，集中管理所有命令的处理逻辑"""
import asyncio
from typing import Optional
from astrbot.api.event import AstrMessageEvent
from astrbot import logger


class Messages:
    """命令响应消息常量"""
    ADMIN_REQUIRED = "⛔ 只有管理员才能使用此命令"
    GROUP_REQUIRED = "❌ 此命令只能在群聊中使用"
    ADAPTER_NOT_FOUND = "❌ 未找到Minecraft平台适配器，请确保适配器已正确注册并启用"
    BIND_SUCCESS = "✅ 成功将本群与Minecraft服务器 {} 绑定"
    BIND_ALREADY = "ℹ️ 此群已经与Minecraft服务器 {} 绑定"
    UNBIND_SUCCESS = "✅ 成功解除本群与Minecraft服务器 {} 的绑定"
    UNBIND_NOT_BOUND = "ℹ️ 此群未与Minecraft服务器 {} 绑定"


class CommandHandler:
    """命令处理器类，用于分离命令处理逻辑"""
    
    def __init__(self, plugin_instance):
        self.plugin = plugin_instance
    
    def _decorator_require_admin(self, func):
        """管理员权限检查装饰器"""
        async def wrapper(event: AstrMessageEvent):
            if not event.is_admin():
                return Messages.ADMIN_REQUIRED
            return await func(event)
        return wrapper
    
    def _decorator_require_group(self, func):
        """群聊环境检查装饰器"""
        async def wrapper(event: AstrMessageEvent):
            group_id = event.get_group_id()
            if not group_id:
                return Messages.GROUP_REQUIRED
            return await func(event)
        return wrapper
    
    async def _get_target_adapter(self, server_name=None):
        """获取目标适配器的公共方法"""
        if server_name:
            for adapter in self.plugin.adapter_router.get_all_adapters():
                if adapter.server_name == server_name or adapter.adapter_id == server_name:
                    return adapter, None
            return None, f"❌ 未找到名为 {server_name} 的Minecraft适配器"
        
        adapter = await self.plugin.get_minecraft_adapter()
        if not adapter:
            return None, Messages.ADAPTER_NOT_FOUND
        return adapter, None

    async def handle_bind_command(self, event: AstrMessageEvent):
        """处理mcbind命令，支持多服务器参数"""
        return await self._decorator_require_admin(self._decorator_require_group(self._handle_bind_logic))(event)
    
    async def handle_unbind_command(self, event: AstrMessageEvent):
        """处理mcunbind命令，支持多服务器参数"""
        return await self._decorator_require_admin(self._decorator_require_group(self._handle_unbind_logic))(event)
    
    async def _handle_binding_command(self, event: AstrMessageEvent, action: str):
        """绑定/解绑命令的公共逻辑"""
        group_id = event.get_group_id()
        tokens = event.message_str.strip().split()
        server_name = tokens[1] if len(tokens) > 1 else None

        adapter, error = await self._get_target_adapter(server_name)
        if error:
            return error

        if action == "bind":
            success = await adapter.bind_group(group_id)
            if success:
                logger.info(f"群聊 {group_id} 与服务器 {adapter.adapter_id} 绑定")
                return Messages.BIND_SUCCESS.format(adapter.adapter_id)
            else:
                return Messages.BIND_ALREADY.format(adapter.adapter_id)
        elif action == "unbind":
            success = await adapter.unbind_group(group_id)
            if success:
                logger.info(f"解除群聊 {group_id} 与服务器 {adapter.server_name} 的绑定")
                return Messages.UNBIND_SUCCESS.format(adapter.server_name)
            else:
                return Messages.UNBIND_NOT_BOUND.format(adapter.server_name)
    
    async def _handle_bind_logic(self, event: AstrMessageEvent):
        """绑定命令的核心逻辑"""
        return await self._handle_binding_command(event, "bind")
    
    async def _handle_unbind_logic(self, event: AstrMessageEvent):
        """解绑命令的核心逻辑"""
        return await self._handle_binding_command(event, "unbind")
    
    async def handle_status_command(self, event: AstrMessageEvent):
        """处理mcstatus命令"""
        group_id = event.get_group_id()
        
        # 获取所有适配器
        adapters = self.plugin.adapter_router.get_all_adapters()
        if not adapters:
            return "❌ 未找到任何Minecraft平台适配器，请确保适配器已正确注册并启用"

        # 构建状态消息
        status_msg = "�� Minecraft适配器状态:\n"
        
        connected_count = 0
        bound_count = 0
        
        for i, adapter in enumerate(adapters, 1):
            # 检查连接状态
            is_connected = await adapter.is_connected()
            if is_connected:
                connected_count += 1
                
            # 检查绑定状态（仅在群聊中检查）
            is_bound = False
            if group_id:
                is_bound = adapter.is_group_bound(group_id)
                if is_bound:
                    bound_count += 1
            
            # 添加适配器状态信息
            status_msg += f"{i}. {adapter.server_name} ({adapter.adapter_id})\n"
            status_msg += f"   连接: {'✅ 已连接' if is_connected else '❌ 未连接'}\n"
            
            if group_id:
                status_msg += f"   绑定: {'✅ 已绑定' if is_bound else '❌ 未绑定'}\n"
            
            # 如果未连接，尝试手动启动连接
            if not is_connected:
                try:
                    adapter.websocket_manager.connected = False
                    adapter.websocket_manager.websocket = None
                    adapter.websocket_manager.should_reconnect = True
                    adapter.websocket_manager.total_retries = 0
                    asyncio.create_task(adapter.websocket_manager.start())
                    status_msg += f"   状态: ⏳ 正在尝试重连...\n"
                except Exception as e:
                    status_msg += f"   状态: ❌ 重连失败: {str(e)}\n"
            
        return status_msg
    
    async def handle_say_command(self, event: AstrMessageEvent):
        """处理mcsay命令"""
        message = event.message_str.replace("mcsay", "", 1).strip()
        if not message:
            return "❓ 请提供要发送的消息内容，例如：/mcsay 大家好"

        sender_name = event.get_sender_name()
        adapters = self.plugin.adapter_router.get_all_adapters()
        
        if not adapters:
            return "❌ 未找到任何Minecraft平台适配器，请确保适配器已正确注册并启用"

        # 检查连接状态
        connected_adapters = [adapter for adapter in adapters if await adapter.is_connected()]
        if not connected_adapters:
            return "❌ 所有Minecraft适配器都未连接，请检查连接状态"

        # 向所有已连接的适配器广播消息
        try:
            await self.plugin.adapter_router.broadcast_message(message, sender_name)
            return ""
        except Exception as e:
            logger.error(f"发送消息到Minecraft服务器时出错: {str(e)}")
            return f"❌ 发送消息失败: {str(e)}"
    
    def handle_help_command(self, event: AstrMessageEvent):
        """处理mc帮助命令，更新多服务器说明"""
        return """
Minecraft相关指令菜单:
qq群:
    '/'或@机器人可发起ai对话
    /mcbind [服务器名] - 绑定当前群聊与指定Minecraft服务器（不填为主服务器）
    /mcunbind [服务器名] - 解除当前群聊与指定Minecraft服务器的绑定（不填为主服务器）
    /mcstatus - 显示所有Minecraft适配器的连接状态和绑定信息
    /mcsay - 向所有已连接的Minecraft服务器发送消息
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
    
    async def handle_rcon_command(self, event: AstrMessageEvent):
        """处理rcon命令"""
        return await self._decorator_require_admin(self._handle_rcon_logic)(event)
    
    async def _handle_rcon_logic(self, event: AstrMessageEvent):
        """RCON命令的核心逻辑"""
        command_to_execute = event.message_str.replace("rcon", "", 1).strip()
        adapter = await self.plugin.get_minecraft_adapter()
        
        if command_to_execute == "重启":
            await self.plugin.rcon_manager.initialize(adapter)
            return "🔄 正在尝试重新连接RCON服务器..."

        success, message = await self.plugin.rcon_manager.execute_command(
            command_to_execute, event.get_sender_id(), adapter
        )
        return message
    
    async def handle_broadcast_config_command(self, event: AstrMessageEvent):
        """处理mc广播设置命令"""
        return await self._decorator_require_admin(self._handle_broadcast_config_logic)(event)
    
    async def _handle_broadcast_config_logic(self, event: AstrMessageEvent):
        """广播配置命令的核心逻辑"""
        command_content = event.message_str.replace("mc广播设置", "", 1).strip()
        if not command_content:
            return self.plugin.broadcast_config_manager.get_current_config_display()
        
        tokens = command_content.split(None, 1)
        if len(tokens) < 2:
            return "❌ 参数不足！\n用法：/mc广播设置 <adapter_id> <消息内容>"
        
        adapter_id, msg_content = tokens[0], tokens[1].strip()
        if not adapter_id or not msg_content:
            return "❌ 参数错误！\n用法：/mc广播设置 <adapter_id> <消息内容>"
        
        # 检查适配器是否存在
        adapter = next((a for a in self.plugin.adapter_router.get_all_adapters() if a.adapter_id == adapter_id), None)
        if not adapter:
            return f"❌ 未找到适配器 {adapter_id}，请检查ID是否正确"
        
        success, message = self.plugin.broadcast_config_manager.set_broadcast_content(adapter_id, msg_content)
        if success:
            logger.info(f"适配器 {adapter_id} 整点广播内容已更新")
        return message
    
    async def handle_broadcast_toggle_command(self, event: AstrMessageEvent):
        """处理mc广播开关命令"""
        return await self._decorator_require_admin(lambda e: self.plugin.broadcast_config_manager.toggle_broadcast()[1])(event)

    async def handle_broadcast_clear_command(self, event: AstrMessageEvent):
        """处理mc广播清除命令"""
        return await self._decorator_require_admin(self._handle_broadcast_clear_logic)(event)
    
    async def _handle_broadcast_clear_logic(self, event: AstrMessageEvent):
        """广播清除命令的核心逻辑"""
        command_content = event.message_str.replace("mc广播清除", "", 1).strip()
        adapter_id = command_content if command_content else None
        _, message = self.plugin.broadcast_config_manager.clear_custom_content(adapter_id)
        return message

    async def handle_broadcast_test_command(self, event: AstrMessageEvent):
        """处理mc广播测试命令"""
        return await self._decorator_require_admin(self._handle_broadcast_test_logic)(event)
    
    async def _handle_broadcast_test_logic(self, event: AstrMessageEvent):
        """广播测试命令的核心逻辑"""
        command_content = event.message_str.replace("mc广播测试", "", 1).strip()
        adapter_id = command_content if command_content else None
        
        logger.info(f"用户 {event.get_sender_id()} 触发了测试广播")
        await self.plugin.broadcast_scheduler.execute_hourly_broadcast()
        return "✅ 已触发测试广播"

    async def handle_custom_broadcast_command(self, event: AstrMessageEvent):
        """处理mc自定义广播命令"""
        return await self._decorator_require_admin(self._handle_custom_broadcast_logic)(event)
    
    async def _handle_custom_broadcast_logic(self, event: AstrMessageEvent):
        """自定义广播命令的核心逻辑"""
        command_content = event.message_str.replace("mc自定义广播", "", 1).strip()
        
        # 解析参数
        parts = command_content.split('|')
        text_content = parts[0].strip() if len(parts) > 0 else ""
        click_value = parts[1].strip() if len(parts) > 1 else ""
        hover_text = parts[2].strip() if len(parts) > 2 else ""

        if not text_content:
            return "❌ 请提供广播的文本内容"

        adapters = self.plugin.adapter_router.get_all_adapters()
        if not adapters:
            return "❌ 未找到任何Minecraft适配器"
        
        try:
            success = await self.plugin.broadcast_sender.send_custom_rich_broadcast(adapters, text_content, click_value, hover_text)
            return "✅ 自定义广播已发送" if success else "❌ 发送自定义广播失败，请查看日志"
        except Exception as e:
            logger.error(f"发送自定义广播时出错: {str(e)}")
            return f"❌ 发送自定义广播时出错: {str(e)}" 