"""命令基类定义"""
from typing import Dict, Any, List, Callable, Awaitable, Optional
from abc import ABC, abstractmethod


class BaseCommand(ABC):
    """命令基类，定义了所有命令的基本接口"""
    
    def __init__(self, prefix: Optional[str] = None, exact_match: bool = False, priority: int = 0):
        """
        初始化命令
        
        Args:
            prefix: 命令前缀，None表示匹配所有以#开头的命令
            exact_match: 是否精确匹配
            priority: 优先级，数字越大优先级越高
        """
        self.prefix = prefix
        self.exact_match = exact_match
        self.priority = priority
    
    def matches(self, message_text: str) -> bool:
        """
        检查消息是否匹配此命令
        
        Args:
            message_text: 消息文本
            
        Returns:
            bool: 是否匹配
        """
        if not message_text:
            return False

        command_text = message_text.strip()

        if self.prefix is None:
            # 通用处理器，匹配任意命令文本
            return bool(command_text)

        if not command_text.startswith(self.prefix):
            return False

        if self.exact_match:
            remaining = command_text[len(self.prefix):]
            return remaining == ""

        # 对于非精确匹配，允许后续存在空白或更多内容
        if len(command_text) == len(self.prefix):
            return True

        next_char = command_text[len(self.prefix)]
        return next_char.isspace()
    
    @abstractmethod
    async def execute(self, 
                     message_text: str,
                     data: Dict[str, Any],
                     server_class,
                     bound_groups: List[str],
                     send_to_groups_callback: Callable[[List[str], str], Awaitable[None]],
                     send_mc_message_callback: Callable[[str], Awaitable[None]],
                     commit_event_callback: Callable,
                     platform_meta,
                     adapter=None) -> bool:
        """
        执行命令
        
        Args:
            message_text: 消息文本
            data: 消息数据
            server_class: 服务器类型对象
            bound_groups: 绑定的群组列表
            send_to_groups_callback: 发送消息到群组的回调函数
            send_mc_message_callback: 发送消息到MC的回调函数
            commit_event_callback: 提交事件的回调函数
            platform_meta: 平台元数据
            adapter: 适配器实例
            
        Returns:
            bool: 是否成功处理了命令
        """
        raise NotImplementedError
    
    def get_help_text(self) -> str:
        """
        获取命令的帮助文本

        Returns:
            str: 帮助文本
        """
        return f"#{self.prefix} - 暂无帮助信息"
    
    def get_priority(self) -> int:
        """获取命令优先级"""
        return self.priority

    def remove_prefix(self, message_text: str) -> str:
        """移除命令前缀并返回剩余内容"""
        if not self.prefix:
            return message_text.strip()
        stripped = message_text.strip()
        if stripped.startswith(self.prefix):
            return stripped[len(self.prefix):].lstrip()
        return stripped
