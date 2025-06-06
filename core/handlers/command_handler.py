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
        """处理mcbind命令，支持多服务器参数"""
        # 仅管理员可以使用此命令
        if not event.is_admin():
            return "⛔ 只有管理员才能使用此命令"

        group_id = event.get_group_id()
        if not group_id:
            return "❌ 此命令只能在群聊中使用"

        # 解析参数，允许 /mcbind <服务器名>
        tokens = event.message_str.strip().split()
        if len(tokens) > 1:
            server_name = tokens[1]
        else:
            server_name = None

        # 获取目标适配器
        adapter = None
        if server_name:
            for a in self.plugin.adapter_router.get_all_adapters():
                if a.server_name == server_name or a.adapter_id == server_name:
                    adapter = a
                    break
            if not adapter:
                return f"❌ 未找到名为 {server_name} 的Minecraft适配器"
        else:
            adapter = await self.plugin.get_minecraft_adapter()
            if not adapter:
                return "❌ 未找到Minecraft平台适配器，请确保适配器已正确注册并启用"

        # 绑定群聊
        success = await adapter.bind_group(group_id)
        if success:
            logger.info(f"群聊 {group_id} 与服务器 {adapter.adapter_id} 绑定")
            return f"✅ 成功将本群与Minecraft服务器 {adapter.adapter_id} 绑定"
        else:
            return f"ℹ️ 此群已经与Minecraft服务器 {adapter.adapter_id} 绑定"
    
    async def handle_unbind_command(self, event: AstrMessageEvent):
        """处理mcunbind命令，支持多服务器参数"""
        # 仅管理员可以使用此命令
        if not event.is_admin():
            return "⛔ 只有管理员才能使用此命令"

        group_id = event.get_group_id()
        if not group_id:
            return "❌ 此命令只能在群聊中使用"

        # 解析参数，允许 /mcunbind <服务器名>
        tokens = event.message_str.strip().split()
        if len(tokens) > 1:
            server_name = tokens[1]
        else:
            server_name = None

        # 获取目标适配器
        adapter = None
        if server_name:
            for a in self.plugin.adapter_router.get_all_adapters():
                if a.server_name == server_name or a.adapter_id == server_name:
                    adapter = a
                    break
            if not adapter:
                return f"❌ 未找到名为 {server_name} 的Minecraft适配器"
        else:
            adapter = await self.plugin.get_minecraft_adapter()
            if not adapter:
                return "❌ 未找到Minecraft平台适配器，请确保适配器已正确注册并启用"

        # 解除绑定
        success = await adapter.unbind_group(group_id)
        if success:
            logger.info(f"解除群聊 {group_id} 与服务器 {adapter.server_name} 的绑定")
            return f"✅ 成功解除本群与Minecraft服务器 {adapter.server_name} 的绑定"
        else:
            return f"ℹ️ 此群未与Minecraft服务器 {adapter.server_name} 绑定"
    
    async def handle_status_command(self, event: AstrMessageEvent):
        """处理mcstatus命令"""
        group_id = event.get_group_id()
        
        # 获取所有适配器
        adapters = self.plugin.adapter_router.get_all_adapters()
        if not adapters:
            return "❌ 未找到任何Minecraft平台适配器，请确保适配器已正确注册并启用"

        # 构建状态消息
        status_msg = "🔌 Minecraft适配器状态:\n"
        
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
        message = event.message_str
        message = message.replace("mcsay", "", 1).strip()
        if not message:
            return "❓ 请提供要发送的消息内容，例如：/mcsay 大家好"

        # 获取发送者信息
        sender_name = event.get_sender_name()

        # 检查是否有可用的适配器
        adapters = self.plugin.adapter_router.get_all_adapters()
        if not adapters:
            return "❌ 未找到任何Minecraft平台适配器，请确保适配器已正确注册并启用"

        # 检查连接状态
        connected_adapters = []
        for adapter in adapters:
            if await adapter.is_connected():
                connected_adapters.append(adapter)

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
        help_msg = """
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
            # 无参数时显示所有配置
            return self.plugin.broadcast_config_manager.get_current_config_display()
        tokens = command_content.split(None, 1)
        if len(tokens) < 2:
            return "❌ 参数不足！\n用法：/mc广播设置 <adapter_id> <消息内容>"
        adapter_id, msg_content = tokens[0], tokens[1].strip()
        if not adapter_id or not msg_content:
            return "❌ 参数错误！\n用法：/mc广播设置 <adapter_id> <消息内容>"
        # 检查适配器是否存在
        adapter = None
        for a in self.plugin.adapter_router.get_all_adapters():
            if a.adapter_id == adapter_id:
                adapter = a
                break
        if not adapter:
            return f"❌ 未找到适配器 {adapter_id}，请检查ID是否正确"
        # 设置内容
        success, message = self.plugin.broadcast_config_manager.set_broadcast_content(adapter_id, msg_content)
        if success:
            logger.info(f"适配器 {adapter_id} 整点广播内容已更新")
        return message
    
    async def handle_broadcast_toggle_command(self, event: AstrMessageEvent):
        """处理mc广播开关命令"""
        if not event.is_admin():
            return "⛔ 只有管理员才能使用此命令"
        
        _, message = self.plugin.broadcast_config_manager.toggle_broadcast()
        return message

    async def handle_broadcast_clear_command(self, event: AstrMessageEvent):
        """处理mc广播清除命令"""
        if not event.is_admin():
            return "⛔ 只有管理员才能使用此命令"
            
        # 解析参数
        command_content = event.message_str.replace("mc广播清除", "", 1).strip()
        adapter_id = command_content if command_content else None

        _, message = self.plugin.broadcast_config_manager.clear_custom_content(adapter_id)
        return message

    async def handle_broadcast_test_command(self, event: AstrMessageEvent):
        """处理mc广播测试命令"""
        # 仅管理员可以使用此命令
        if not event.is_admin():
            return "⛔ 只有管理员才能使用此命令"
        
        # 解析参数
        command_content = event.message_str.replace("mc广播测试", "", 1).strip()
        adapter_id = command_content if command_content else None
        
        logger.info(f"用户 {event.get_sender_id()} 触发了测试广播")

        # 执行测试广播
        await self.plugin.broadcast_scheduler.execute_hourly_broadcast()
        
        return "✅ 已触发测试广播"

    async def handle_custom_broadcast_command(self, event: AstrMessageEvent):
        """处理mc自定义广播命令"""
        if not event.is_admin():
            return "⛔ 只有管理员才能使用此命令"

        command_content = event.message_str.replace("mc自定义广播", "", 1).strip()
        
        # 解析参数
        parts = command_content.split('|')
        text_content = parts[0].strip() if len(parts) > 0 else ""
        click_value = parts[1].strip() if len(parts) > 1 else ""
        hover_text = parts[2].strip() if len(parts) > 2 else ""

        if not text_content:
            return "❌ 请提供广播的文本内容"

        # 获取所有适配器
        adapters = self.plugin.adapter_router.get_all_adapters()
        if not adapters:
            return "❌ 未找到任何Minecraft适配器"
        
        try:
            success = await self.plugin.broadcast_sender.send_custom_rich_broadcast(adapters, text_content, click_value, hover_text)
            if success:
                return "✅ 自定义广播已发送"
            else:
                return "❌ 发送自定义广播失败，请查看日志"
        except Exception as e:
            logger.error(f"发送自定义广播时出错: {str(e)}")
            return f"❌ 发送自定义广播时出错: {str(e)}" 