import asyncio
import datetime
import json
from typing import Optional, List, Dict, Any
from pathlib import Path
from astrbot import logger
from astrbot.core.star.star_tools import StarTools
from ..utils.wiki_utils import WikiUtils


class BroadcastManager:
    """整点广播和自定义广播管理器"""
    
    def __init__(self, data_dir: Optional[str] = None):
        # 数据目录设置
        if data_dir is None:
            self.data_dir = StarTools.get_data_dir("mcqq")
        else:
            self.data_dir = Path(data_dir)
        
        # 确保数据目录存在
        self.data_dir.mkdir(parents=True, exist_ok=True)
        
        # 配置文件路径
        self.config_file = self.data_dir / "broadcast_config.json"
        
        # 整点广播相关属性
        self.hourly_broadcast_enabled: bool = True
        # 固定的发送延迟间隔（秒）
        self.send_interval: float = 0.1
        
        # 默认的整点广播内容（支持富文本的JSON格式）
        self.hourly_broadcast_content = [
            {
                "text": "🕐 整点报时！当前时间：{time}",
                "color": "aqua", 
                "bold": False,
                "click_command": "",
                "hover_text": "🤖 AstrBot 整点报时系统"
            }
        ]
        self.hourly_broadcast_task: Optional[asyncio.Task] = None
        
        # 用户自定义的广播内容（用于覆盖默认内容）
        self.custom_broadcast_content: Optional[List[Dict[str, Any]]] = None
        
        # 加载保存的配置
        self.load_config()
    
    def load_config(self):
        """从文件加载广播配置"""
        try:
            if self.config_file.exists():
                with open(self.config_file, 'r', encoding='utf-8') as f:
                    config = json.load(f)
                
                # 加载广播开关状态
                self.hourly_broadcast_enabled = config.get("hourly_broadcast_enabled", True)
                
                # 加载自定义广播内容
                custom_content = config.get("custom_broadcast_content")
                if custom_content:
                    self.custom_broadcast_content = custom_content
                    logger.info("已加载保存的广播配置")
                
        except Exception as e:
            logger.error(f"加载广播配置失败: {e}")
    
    def save_config(self):
        """保存广播配置到文件"""
        try:
            config = {
                "hourly_broadcast_enabled": self.hourly_broadcast_enabled,
                "custom_broadcast_content": self.custom_broadcast_content
            }
            
            with open(self.config_file, 'w', encoding='utf-8') as f:
                json.dump(config, f, ensure_ascii=False, indent=2)
            
            logger.debug("广播配置已保存")
            
        except Exception as e:
            logger.error(f"保存广播配置失败: {e}")
    
    async def start_hourly_broadcast(self, broadcast_callback):
        """启动整点广播任务"""
        while True:
            # 等待到整点
            now = datetime.datetime.now()
            next_hour = now.replace(minute=0, second=0, microsecond=0) + datetime.timedelta(hours=1)
            await asyncio.sleep((next_hour - now).total_seconds())

            # 执行整点广播
            await self.execute_hourly_broadcast(broadcast_callback)
    
    async def execute_hourly_broadcast(self, broadcast_callback):
        """执行整点广播"""
        # 检查广播是否开启
        if not self.hourly_broadcast_enabled:
            logger.debug("整点广播已关闭，跳过广播")
            return

        # 使用自定义内容或默认内容
        content = self.custom_broadcast_content or self.hourly_broadcast_content
        
        # 发送原有的整点广播消息
        success = await broadcast_callback(content)
        if success:
            logger.info("整点广播已成功执行")
        else:
            logger.warning("整点广播执行失败")
        
        # 获取并发送随机Wiki内容
        try:
            wiki_content = await WikiUtils.get_random_wiki_content()
            if wiki_content:
                # 构建Wiki广播内容
                wiki_broadcast_content = [{
                    "text": wiki_content,
                    "color": "yellow",
                    "bold": False,
                    "click_command": "",
                    "hover_text": "🎓 来自 Minecraft Wiki 的随机知识"
                }]
                
                # 等待一小段时间再发送Wiki内容，避免消息过于密集
                await asyncio.sleep(2.0)
                
                # 发送Wiki广播
                wiki_success = await broadcast_callback(wiki_broadcast_content)
                if wiki_success:
                    logger.info("Wiki随机内容广播已成功执行")
                else:
                    logger.warning("Wiki随机内容广播执行失败")
            else:
                logger.warning("获取Wiki随机内容失败，跳过Wiki广播")
        except Exception as e:
            logger.error(f"Wiki广播执行时出错: {str(e)}")
    
    def set_broadcast_content(self, config_string: str) -> tuple[bool, str]:
        """
        解析并设置广播内容
        
        Args:
            config_string: 配置字符串
            
        Returns:
            tuple[bool, str]: (成功标志, 结果消息)
        """
        try:
            new_content = self._parse_broadcast_config(config_string)
            self.custom_broadcast_content = new_content
            
            # 保存配置到文件
            self.save_config()
            
            # 显示设置结果
            config_display = self._format_broadcast_config_display()
            return True, f"✅ 整点广播内容已更新并保存:\n{config_display}"
            
        except Exception as e:
            return False, f"❌ 解析广播配置时出错: {str(e)}\n\n💡 格式说明:\n" \
                         f"🎨 富文本: [文本,颜色,粗体(true/false),点击命令,悬浮文本]|[下一个组件]\n" \
                         f"📝 简单: 直接输入文本内容\n" \
                         f"📋 示例: 🕐,gold,true,,|报时：{{time}},aqua,false,/time,点击查询"
    
    def toggle_broadcast(self) -> tuple[bool, str]:
        """
        切换广播开关状态
        
        Returns:
            tuple[bool, str]: (新状态, 状态消息)
        """
        self.hourly_broadcast_enabled = not self.hourly_broadcast_enabled
        
        # 保存配置到文件
        self.save_config()
        
        status = "开启" if self.hourly_broadcast_enabled else "关闭"
        return self.hourly_broadcast_enabled, f"✅ 整点广播已{status}并保存设置"
    
    def clear_custom_content(self) -> tuple[bool, str]:
        """
        清除自定义广播内容，恢复为默认内容
        
        Returns:
            tuple[bool, str]: (成功标志, 结果消息)
        """
        self.custom_broadcast_content = None
        
        # 保存配置到文件
        self.save_config()
        
        return True, "✅ 已清除自定义广播内容，恢复为默认内容并保存设置"
    
    def get_current_config_display(self) -> str:
        """获取当前配置的显示文本"""
        current_config = self._format_broadcast_config_display()
        return f"❓ 当前整点广播配置:\n{current_config}\n\n💡 使用方法:\n" \
               f"📝 简单模式: mc广播设置 [文本内容]\n" \
               f"🎨 富文本模式: mc广播设置 [文本,颜色,点击命令,悬浮文本]|[文本2,颜色2,点击命令2,悬浮文本2]\n" \
               f"📋 示例: mc广播设置 🕐,gold,true,,|整点报时！时间：{{time}},aqua,false,/time query daytime,点击查询时间"
    
    def _parse_broadcast_config(self, config_string: str) -> List[Dict[str, Any]]:
        """解析广播配置字符串"""
        # 如果包含 | 符号，说明是富文本模式
        if "|" in config_string:
            components = []
            parts = config_string.split("|")
            
            for part in parts:
                part = part.strip()
                if not part:
                    continue
                    
                # 解析每个组件: 文本,颜色,粗体,点击命令,悬浮文本
                params = [p.strip() for p in part.split(",")]
                
                if len(params) < 1:
                    raise ValueError("每个组件至少需要包含文本内容")
                
                component = {
                    "text": params[0] if params[0] else "",
                    "color": params[1] if len(params) > 1 and params[1] else "white",
                    "bold": params[2].lower() == "true" if len(params) > 2 and params[2] else False,
                    "click_command": params[3] if len(params) > 3 and params[3] else "",
                    "hover_text": params[4] if len(params) > 4 and params[4] else ""
                }
                
                if component["text"]:  # 只添加非空文本的组件
                    components.append(component)
            
            if not components:
                raise ValueError("至少需要一个有效的文本组件")
                
            return components
        else:
            # 简单模式：单个文本
            return [{
                "text": config_string,
                "color": "aqua",
                "bold": False,
                "click_command": "/time query daytime",
                "hover_text": "🤖 AstrBot 整点报时系统"
            }]
    
    def _format_broadcast_config_display(self) -> str:
        """格式化显示当前广播配置"""
        # 使用自定义内容或默认内容
        content = self.custom_broadcast_content or self.hourly_broadcast_content
        
        lines = []
        for i, component in enumerate(content, 1):
            line = f"  {i}. 文本: {component['text']}"
            if component['color'] != 'white':
                line += f" | 颜色: {component['color']}"
            if component['bold']:
                line += f" | 粗体: 是"
            if component['click_command']:
                line += f" | 点击: {component['click_command']}"
            if component['hover_text']:
                line += f" | 悬浮: {component['hover_text']}"
            lines.append(line)
        return "\n".join(lines)
    
    async def send_rich_broadcast(self, adapter, components: List[Dict[str, Any]]) -> bool:
        """发送支持富文本格式的广播消息"""
        if not adapter.connected or not adapter.websocket:
            logger.error("无法发送广播：WebSocket未连接")
            return False

        try:
            # 每个组件单独发送一条消息
            return await self._send_separately(adapter, components)

        except Exception as e:
            logger.error(f"发送富文本广播消息时出错: {str(e)}")
            return False
    
    async def _send_separately(self, adapter, components: List[Dict[str, Any]]) -> bool:
        """每个组件单独发送一条消息"""
        success_count = 0
        total_components = len(components)
        
        # 逐个发送每个组件
        for i, component in enumerate(components):
            # 处理时间变量替换
            current_time = datetime.datetime.now().strftime("%H:%M")
            text_content = component["text"].format(time=current_time)
            
            # 构建单个消息组件
            msg_component = {
                "type": "text",
                "data": {
                    "text": text_content,
                    "color": component.get("color", "white"),
                    "bold": component.get("bold", False)
                }
            }
            
            # 添加悬浮事件（如果有）
            if component.get("hover_text"):
                msg_component["data"]["hover_event"] = {
                    "action": "SHOW_TEXT",
                    "text": [
                        {
                            "text": component["hover_text"],
                            "color": "yellow",
                            "bold": True
                        }
                    ]
                }
            
            # 添加点击事件（如果有）
            if component.get("click_command"):
                msg_component["data"]["click_event"] = {
                    "action": "SUGGEST_COMMAND",
                    "value": component["click_command"]
                }

            # 构建单条广播消息
            broadcast_msg = {
                "api": "broadcast",
                "data": {
                    "message": [msg_component]  # 单个组件的数组
                }
            }

            # 打印要发送的JSON消息，便于调试
            logger.debug(f"发送第 {i+1}/{total_components} 条广播消息: {json.dumps(broadcast_msg, ensure_ascii=False)}")

            try:
                # 发送单条消息
                await adapter.websocket.send(json.dumps(broadcast_msg))
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
    
    async def send_custom_rich_broadcast(self, adapter, text_content: str, click_value: str, hover_text: str) -> bool:
        """发送自定义富文本广播消息"""
        if not adapter.connected or not adapter.websocket:
            logger.error("无法发送自定义广播：WebSocket未连接")
            return False

        try:
            # 构建自定义富文本广播消息
            broadcast_msg = {
                "api": "broadcast",
                "data": {
                    "message": [
                        {
                            "type": "text",
                            "data": {
                                "text": "[管理员公告] ",
                                "color": "red",
                                "bold": True
                            }
                        },
                        {
                            "type": "text", 
                            "data": {
                                "text": text_content,
                                "color": "white",
                                "bold": False,
                                "hover_event": {
                                    "action": "SHOW_TEXT",
                                    "text": [
                                        {
                                            "text": hover_text,
                                            "color": "gold",
                                            "bold": True
                                        }
                                    ]
                                },
                                "click_event": {
                                    "action": "SUGGEST_COMMAND",
                                    "value": click_value
                                }
                            }
                        }
                    ]
                }
            }

            # 打印要发送的JSON消息，便于调试
            logger.debug(f"发送的自定义富文本广播消息: {json.dumps(broadcast_msg, ensure_ascii=False)}")

            # 发送消息
            await adapter.websocket.send(json.dumps(broadcast_msg))
            return True

        except Exception as e:
            logger.error(f"发送自定义富文本广播消息时出错: {str(e)}")
            return False
    
    def is_enabled(self) -> bool:
        """检查整点广播是否启用"""
        return self.hourly_broadcast_enabled 