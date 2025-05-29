from typing import List


class BotFilter:
    """假人/机器人玩家过滤器"""
    
    def __init__(self, filter_enabled: bool = True, prefix_list: List[str] = None, suffix_list: List[str] = None):
        """
        初始化假人过滤器
        
        Args:
            filter_enabled: 是否启用过滤
            prefix_list: 假人名称前缀列表
            suffix_list: 假人名称后缀列表
        """
        self.filter_enabled = filter_enabled
        self.bot_prefix = prefix_list or ["bot_", "Bot_"]
        self.bot_suffix = suffix_list or []
    
    def is_bot_player(self, player_name: str) -> bool:
        """
        检查玩家是否为假人
        
        Args:
            player_name: 玩家名称
            
        Returns:
            bool: 是假人返回True，否则返回False
        """
        if not self.filter_enabled:
            return False
            
        # 确保player_name是字符串
        if not isinstance(player_name, str):
            return False
            
        # 检查前缀
        for prefix in self.bot_prefix:
            if player_name.startswith(prefix):
                return True
                
        # 检查后缀
        for suffix in self.bot_suffix:
            if player_name.endswith(suffix):
                return True
                
        return False
    
    def update_config(self, filter_enabled: bool = None, prefix_list: List[str] = None, suffix_list: List[str] = None):
        """
        更新过滤器配置
        
        Args:
            filter_enabled: 是否启用过滤
            prefix_list: 假人名称前缀列表
            suffix_list: 假人名称后缀列表
        """
        if filter_enabled is not None:
            self.filter_enabled = filter_enabled
        if prefix_list is not None:
            self.bot_prefix = prefix_list
        if suffix_list is not None:
            self.bot_suffix = suffix_list 