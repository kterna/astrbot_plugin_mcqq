import json
from typing import List, Dict, Any, Optional
from astrbot import logger


class MessageBuilder:
    """消息构建工具类，用于构建发送到Minecraft服务器的各种消息格式"""
    
    @staticmethod
    def create_text_event(
        text: str,
        color: str = "white",
        bold: bool = False,
        italic: bool = False,
        underlined: bool = False,
        strikethrough: bool = False,
        obfuscated: bool = False,
        font: Optional[str] = None,
        insertion: Optional[str] = None
    ) -> Dict[str, Any]:
        """创建基础文本组件"""
        return {
            "text": text,
            "color": color,
            "font": font,
            "bold": bold,
            "italic": italic,
            "underlined": underlined,
            "strikethrough": strikethrough,
            "obfuscated": obfuscated,
            "insertion": insertion
        }
    
    @staticmethod
    def add_hover_event(component: Dict[str, Any], hover_text: str, hover_color: str = "aqua", hover_bold: bool = True) -> Dict[str, Any]:
        """为组件添加悬浮事件"""
        component["hover_event"] = {
            "action": "SHOW_TEXT",
            "text": [
                {
                    "text": hover_text,
                    "color": hover_color,
                    "font": None,
                    "bold": hover_bold,
                    "italic": False,
                    "underlined": True,
                    "strikethrough": False,
                    "obfuscated": False,
                    "insertion": None
                }
            ]
        }
        return component
    
    @staticmethod
    def add_click_event(component: Dict[str, Any], click_value: str, click_action: str = "SUGGEST_COMMAND") -> Dict[str, Any]:
        """为组件添加点击事件"""
        # 验证点击事件类型
        valid_actions = ["SUGGEST_COMMAND", "RUN_COMMAND", "OPEN_URL"]
        if click_action.upper() not in valid_actions:
            click_action = "SUGGEST_COMMAND"
        
        component["click_event"] = {
            "action": click_action.upper(),
            "value": click_value
        }
        return component
    
    @staticmethod
    def create_broadcast_message(components: List[Dict[str, Any]]) -> Dict[str, Any]:
        """创建广播消息"""
        message_components = []
        for component in components:
            message_components.append({
                "type": "text",
                "data": component
            })
        
        return {
            "api": "broadcast",
            "data": {
                "message": message_components
            }
        }
    
    @staticmethod
    def create_private_message(uuid: str, component: Dict[str, Any], nickname: str = "") -> Dict[str, Any]:
        """创建私聊消息"""
        return {
            "api": "send_private_msg",
            "data": {
                "uuid": uuid,
                "nickname": nickname,
                "message": [{
                    "type": "text",
                    "data": component
                }]
            },
            "echo": "1"
        }
    
    @staticmethod
    def create_simple_broadcast(message: str, sender: str = None) -> Dict[str, Any]:
        """创建简单的广播消息"""
        # 构建消息文本
        if sender:
            mc_message = f"{sender}: {message}"
        else:
            mc_message = message
        
        # 创建文本组件
        text_component = MessageBuilder.create_text_event(mc_message)
        
        # 创建广播消息
        return MessageBuilder.create_broadcast_message([text_component])
    
    @staticmethod
    def create_rich_broadcast(
        text: str,
        color: str = "#E6E6FA",
        bold: bool = False,
        click_url: str = "",
        hover_text: str = "",
        images: List[str] = None,
        click_action: str = "OPEN_URL"
    ) -> Dict[str, Any]:
        """创建富文本广播消息"""
        # 创建基础文本组件
        components = [MessageBuilder.create_text_event(text, color, bold)]
        component = components[0]
        
        # 添加悬浮事件
        if hover_text:
            MessageBuilder.add_hover_event(component, hover_text, "gold", True)
        
        # 添加点击事件
        if click_url:
            MessageBuilder.add_click_event(component, click_url, click_action)
        # 添加图片事件
        if images:
            for image_url in images:
                if not image_url:
                    continue
                image_component = MessageBuilder.create_text_event(f"[图片][{image_url}]")
                MessageBuilder.add_click_event(image_component, image_url, "OPEN_URL")
                components.append(image_component)
        # 创建广播消息
        return MessageBuilder.create_broadcast_message(components)
    
    @staticmethod
    def create_admin_announcement(
        text: str,
        click_value: str = "",
        hover_text: str = "",
        click_action: str = "SUGGEST_COMMAND"
    ) -> Dict[str, Any]:
        """创建管理员公告消息"""
        components = []
        
        # 添加管理员公告前缀
        admin_prefix = MessageBuilder.create_text_event(
            "[管理员公告] ",
            color="red",
            bold=True
        )
        components.append(admin_prefix)
        
        # 添加主要内容
        main_content = MessageBuilder.create_text_event(
            text,
            color="white",
            bold=False
        )
        
        # 添加悬浮和点击事件
        if hover_text:
            MessageBuilder.add_hover_event(main_content, hover_text, "gold", True)
        
        if click_value:
            MessageBuilder.add_click_event(main_content, click_value, click_action)
        
        components.append(main_content)
        
        # 创建广播消息
        return MessageBuilder.create_broadcast_message(components)
    
    @staticmethod
    def log_message(message: Dict[str, Any], message_type: str = "消息"):
        """记录要发送的消息到日志"""
        logger.debug(f"发送的{message_type}: {json.dumps(message, ensure_ascii=False)}")
    
    @staticmethod
    def validate_component(component: Dict[str, Any]) -> bool:
        """验证消息组件是否有效"""
        # 检查必需的字段
        if not isinstance(component, dict):
            return False
        
        # 检查是否有文本内容
        text = component.get("text", "")
        if not text or not isinstance(text, str):
            return False
        
        return True
    
    @staticmethod
    def clean_component(component: Dict[str, Any]) -> Dict[str, Any]:
        """清理组件，移除None值"""
        cleaned = {}
        for key, value in component.items():
            if value is not None:
                cleaned[key] = value
        return cleaned 