import json
import os
from typing import Dict, List
from astrbot import logger


class GroupBindingManager:
    """群聊与服务器绑定关系管理器"""
    
    def __init__(self, data_dir: str):
        """
        初始化绑定管理器
        
        Args:
            data_dir: 数据目录路径
        """
        self.data_dir = data_dir
        self.bindings_file = os.path.join(data_dir, "group_bindings.json")
        self.group_bindings: Dict[str, List[str]] = {}
    
    def _ensure_file_exists(self):
        """确保绑定文件和目录存在"""
        os.makedirs(os.path.dirname(self.bindings_file), exist_ok=True)
        if not os.path.exists(self.bindings_file):
            with open(self.bindings_file, 'w', encoding='utf-8') as f:
                json.dump({}, f)
    
    def _safe_file_operation(self, operation_func, default_value=None):
        """安全的文件操作包装器"""
        try:
            return operation_func()
        except Exception as e:
            logger.error(f"文件操作失败: {str(e)}")
            return default_value
        
    def load_bindings(self) -> Dict[str, List[str]]:
        """从文件加载群聊与服务器的绑定关系"""
        def _load():
            self._ensure_file_exists()
            with open(self.bindings_file, 'r', encoding='utf-8') as f:
                return json.load(f)
        
        loaded_bindings = self._safe_file_operation(_load, {})
        if loaded_bindings is not None:
            self.group_bindings = loaded_bindings
            logger.info(f"已从 {self.bindings_file} 加载群聊绑定配置")
        else:
            self.group_bindings = {}
            logger.info("绑定配置文件不存在或加载失败，使用空配置")
        
        return self.group_bindings

    def save_bindings(self):
        """保存群聊与服务器的绑定关系到文件"""
        def _save():
            self._ensure_file_exists()
            with open(self.bindings_file, 'w', encoding='utf-8') as f:
                json.dump(self.group_bindings, f, ensure_ascii=False, indent=2)
        
        if self._safe_file_operation(_save) is not False:
            logger.info(f"已保存群聊绑定配置到 {self.bindings_file}")

    def bind_group(self, group_id: str, server_name: str) -> bool:
        """
        绑定群聊与Minecraft服务器
        
        Args:
            group_id: 群聊ID
            server_name: 服务器名称
            
        Returns:
            bool: 绑定成功返回True，已存在返回False
        """
        if server_name not in self.group_bindings:
            self.group_bindings[server_name] = []

        if group_id in self.group_bindings[server_name]:
            return False  # 已经绑定

        self.group_bindings[server_name].append(group_id)
        self.save_bindings()
        return True

    def unbind_group(self, group_id: str, server_name: str) -> bool:
        """
        解除群聊与Minecraft服务器的绑定
        
        Args:
            group_id: 群聊ID
            server_name: 服务器名称
            
        Returns:
            bool: 解绑成功返回True，不存在返回False
        """
        if server_name in self.group_bindings and group_id in self.group_bindings[server_name]:
            self.group_bindings[server_name].remove(group_id)
            self.save_bindings()
            return True
        return False

    def is_group_bound(self, group_id: str, server_name: str) -> bool:
        """
        检查群聊是否与Minecraft服务器绑定
        
        Args:
            group_id: 群聊ID
            server_name: 服务器名称
            
        Returns:
            bool: 已绑定返回True，未绑定返回False
        """
        return server_name in self.group_bindings and group_id in self.group_bindings[server_name]
    
    def get_bound_groups(self, server_name: str) -> List[str]:
        """
        获取服务器绑定的群聊列表
        
        Args:
            server_name: 服务器名称
            
        Returns:
            List[str]: 绑定的群聊ID列表
        """
        return self.group_bindings.get(server_name, [])
    
    def get_all_bindings(self) -> Dict[str, List[str]]:
        """
        获取所有绑定关系
        
        Returns:
            Dict[str, List[str]]: 所有绑定关系字典
        """
        return self.group_bindings.copy() 