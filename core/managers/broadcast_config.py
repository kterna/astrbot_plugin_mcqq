import json
import datetime
from typing import Optional, List, Dict, Any
from pathlib import Path
from astrbot import logger
from astrbot.core.star.star_tools import StarTools


class BroadcastConfigManager:
    """管理广播配置"""

    def __init__(self, data_dir: Optional[str] = None):
        """
        初始化配置管理器。

        Args:
            data_dir (Optional[str], optional): 数据目录路径. Defaults to None.
        """
        if data_dir is None:
            self.data_dir = StarTools.get_data_dir("mcqq")
        else:
            self.data_dir = Path(data_dir)

        self.data_dir.mkdir(parents=True, exist_ok=True)
        self.config_file = self.data_dir / "broadcast_config.json"

        self.hourly_broadcast_enabled: bool = True
        self.hourly_broadcast_content = [
            {
                "text": "🐷猪花广播为您服务！🕐现在是{time}。[查看命令指南]",
                "color": "aqua",
                "bold": False,
                "click_event": {
                    "action": "SUGGEST_COMMAND",
                    "value": "#命令指南"
                },
                "hover_event": {
                    "action": "SHOW_TEXT",
                    "contents": [
                        {
                            "text": "🤖 点击查看服务器命令指南"
                        }
                    ]
                },
                "click_action": "SUGGEST_COMMAND"
            }
        ]
        self.custom_broadcast_content: Optional[dict] = None

        self.load_config()

    def _safe_file_operation(self, operation_func, operation_name: str, default_value=None):
        """安全的文件操作包装器"""
        try:
            return operation_func()
        except Exception as e:
            logger.error(f"{operation_name}失败: {e}")
            return default_value

    def load_config(self):
        """从文件加载广播配置"""
        def _load():
            if self.config_file.exists():
                with open(self.config_file, 'r', encoding='utf-8') as f:
                    config = json.load(f)
                self.hourly_broadcast_enabled = config.get("hourly_broadcast_enabled", True)
                self.custom_broadcast_content = config.get("custom_broadcast_content")
                logger.info("已加载保存的广播配置")
                return True
            return False
        
        self._safe_file_operation(_load, "加载广播配置", False)

    def save_config(self):
        """保存广播配置到文件"""
        def _save():
            config = {
                "hourly_broadcast_enabled": self.hourly_broadcast_enabled,
                "custom_broadcast_content": self.custom_broadcast_content
            }
            with open(self.config_file, 'w', encoding='utf-8') as f:
                json.dump(config, f, ensure_ascii=False, indent=2)
            logger.debug("广播配置已保存")
            return True
        
        self._safe_file_operation(_save, "保存广播配置")

    def set_broadcast_content(self, adapter_id: str, config_string: str) -> tuple[bool, str]:
        """解析并设置指定适配器的广播内容"""
        try:
            new_content = self._parse_broadcast_config(config_string)
            if self.custom_broadcast_content is None:
                self.custom_broadcast_content = {}
            self.custom_broadcast_content[adapter_id] = new_content
            self.save_config()
            config_display = self._format_broadcast_config_display(adapter_id)
            return True, f"✅ 适配器 {adapter_id} 的整点广播内容已更新并保存:\n{config_display}"
        except Exception as e:
            return False, f"❌ 解析广播配置时出错: {str(e)}\n\n💡 格式说明:\n🎨 富文本: [文本,颜色,粗体(true/false),点击命令,悬浮文本]|[下一个组件]\n📝 简单: 直接输入文本内容\n📋 示例: 🕐,gold,true,,|报时：{{time}},aqua,false,/time,点击查询"

    def toggle_broadcast(self) -> tuple[bool, str]:
        """切换广播开关状态"""
        self.hourly_broadcast_enabled = not self.hourly_broadcast_enabled
        self.save_config()
        status = "开启" if self.hourly_broadcast_enabled else "关闭"
        return self.hourly_broadcast_enabled, f"✅ 整点广播已{status}并保存设置"

    def clear_custom_content(self, adapter_id: str = None) -> tuple[bool, str]:
        """清除指定适配器的自定义广播内容"""
        if self.custom_broadcast_content is not None:
            if adapter_id:
                if adapter_id in self.custom_broadcast_content:
                    del self.custom_broadcast_content[adapter_id]
                    self.save_config()
                    return True, f"✅ 已清除适配器 {adapter_id} 的自定义广播内容，恢复为默认内容并保存设置"
                else:
                    return False, f"ℹ️ 适配器 {adapter_id} 没有自定义广播内容"
            else:
                self.custom_broadcast_content = None
                self.save_config()
                return True, "✅ 已清除所有自定义广播内容，恢复为默认内容并保存设置"
        return False, "ℹ️ 没有自定义广播内容"

    def get_current_config_display(self, adapter_id: str = None) -> str:
        """获取指定适配器的当前配置的显示文本"""
        if adapter_id:
            content = self.get_broadcast_content(adapter_id)
            title = f"适配器 {adapter_id} 的自定义广播内容" if self.custom_broadcast_content and adapter_id in self.custom_broadcast_content else f"适配器 {adapter_id} 的默认整点广播内容"
            lines = [f"📋 {title}:"]
            lines.append(self._format_content_to_display(content))
            return "\n".join(lines)
        else:
            lines = ["📋 所有适配器自定义广播内容:"]
            if self.custom_broadcast_content:
                for aid, content in self.custom_broadcast_content.items():
                    lines.append(f"- {aid}:")
                    lines.append(self._format_content_to_display(content))
            return "\n".join(lines)

    def _format_content_to_display(self, content: list) -> str:
        """Helper to format a list of components for display."""
        lines = []
        for i, component in enumerate(content, 1):
            line_parts = [f"  {i}. 文本: {component['text']}"]
            
            if component.get('color', 'white') != 'white':
                line_parts.append(f"颜色: {component['color']}")
            if component.get('bold'):
                line_parts.append("粗体: 是")
            
            if "click_event" in component and component["click_event"].get("value"):
                click_event = component["click_event"]
                line_parts.append(f"点击: {click_event['value']}")
                line_parts.append(f"点击类型: {click_event.get('action', 'SUGGEST_COMMAND')}")
            
            if "hover_event" in component:
                hover_event = component["hover_event"]
                if hover_event.get("contents") and len(hover_event["contents"]) > 0:
                    hover_text = hover_event["contents"][0].get("text", "")
                    if hover_text:
                        line_parts.append(f"悬浮: {hover_text}")
            
            lines.append(" | ".join(line_parts))
        return "\n".join(lines)

    def _parse_broadcast_config(self, config_string: str) -> List[Dict[str, Any]]:
        """解析广播配置字符串"""
        if "|" not in config_string:
            return [{"text": config_string, "color": "white", "bold": False}]
        
        components = []
        for part in config_string.split("|"):
            part = part.strip()
            if not part:
                continue
            
            fields = [f.strip() for f in part.split(",")]
            if len(fields) < 1:
                continue
            
            text, color, bold, click_value, hover_text = (
                fields[0],
                fields[1] if len(fields) > 1 and fields[1] else "white",
                fields[2].lower() == 'true' if len(fields) > 2 and fields[2] else False,
                fields[3] if len(fields) > 3 and fields[3] else None,
                fields[4] if len(fields) > 4 and fields[4] else None
            )

            component = {
                "text": text.replace("{{time}}", datetime.datetime.now().strftime("%H:%M")),
                "color": color,
                "bold": bold
            }

            if click_value:
                component["click_event"] = {"action": "SUGGEST_COMMAND", "value": click_value}
            
            if hover_text:
                component["hover_event"] = {"action": "SHOW_TEXT", "contents": [{"text": hover_text}]}
            
            components.append(component)
        return components

    def _format_broadcast_config_display(self, adapter_id: str) -> str:
        """格式化广播配置以便显示"""
        content = self.get_broadcast_content(adapter_id)
        return self._format_content_to_display(content)

    def is_enabled(self) -> bool:
        """检查广播是否启用"""
        return self.hourly_broadcast_enabled

    def get_broadcast_content(self, adapter_id: str) -> list:
        """获取指定适配器的广播内容"""
        if self.custom_broadcast_content and adapter_id in self.custom_broadcast_content:
            return self.custom_broadcast_content[adapter_id]
        return self.hourly_broadcast_content 