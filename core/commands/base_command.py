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
        if not message_text.startswith("#"):
            return False
            
        if self.prefix is None:
            # 通用处理器，匹配所有#开头的消息
            return True
            
        command_part = message_text[1:]  # 去掉#
        
        if self.exact_match:
            return command_part == self.prefix
        else:
            return command_part.startswith(self.prefix)
    
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
