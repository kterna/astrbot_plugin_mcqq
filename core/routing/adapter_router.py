from typing import Dict, List, Optional, Set
import asyncio
import json
from pathlib import Path

from astrbot import logger
from ..adapters.base_adapter import BaseMinecraftAdapter


class AdapterRouter:
    """适配器路由管理器，负责管理多个适配器之间的自动消息转发"""
    
    def __init__(self, data_dir: str):
        self.data_dir = Path(data_dir)
        self.adapters: Dict[str, BaseMinecraftAdapter] = {}
        
    def register_adapter(self, adapter: BaseMinecraftAdapter):
        """注册适配器"""
        adapter_id = adapter.adapter_id
        self.adapters[adapter_id] = adapter
        logger.info(f"已注册适配器: {adapter_id} ({adapter.server_name})")
        
    def unregister_adapter(self, adapter_id: str):
        """注销适配器"""
        if adapter_id in self.adapters:
            del self.adapters[adapter_id]
            logger.info(f"已注销适配器: {adapter_id}")
            
    def get_adapter(self, adapter_id: str) -> Optional[BaseMinecraftAdapter]:
        """获取指定的适配器"""
        return self.adapters.get(adapter_id)
        
    def get_all_adapters(self) -> List[BaseMinecraftAdapter]:
        """获取所有已注册的适配器"""
        return list(self.adapters.values())
    
    async def _route_message(self, source_adapter_id: str, message_formatter, *args):
        """统一的消息路由模板方法"""
        source_adapter = self.adapters.get(source_adapter_id)
        if not source_adapter:
            logger.warning(f"源适配器 {source_adapter_id} 未找到")
            return
        
        # 使用格式化函数生成消息
        message = message_formatter(source_adapter.server_name, *args)
        logger.debug(f"路由消息: {message}")
        
        # 向所有其他适配器发送消息
        await self._broadcast_to_others(source_adapter_id, message)
        
    async def route_chat_message(self, source_adapter_id: str, message: str, sender: str):
        """转发聊天消息到所有其他适配器"""
        logger.debug(f"路由聊天消息: 来源={source_adapter_id}, 发送者={sender}, 消息={message}")
        logger.debug(f"当前注册的适配器: {list(self.adapters.keys())}")
        
        await self._route_message(
            source_adapter_id,
            lambda server_name, msg, sndr: f"[{server_name}] {sndr}: {msg}",
            message, sender
        )
        
    async def route_player_join(self, source_adapter_id: str, player_name: str):
        """转发玩家加入消息到所有其他适配器"""
        logger.debug(f"路由玩家加入: 来源={source_adapter_id}, 玩家={player_name}")
        
        await self._route_message(
            source_adapter_id,
            lambda server_name, player: f"[{server_name}] {player} 加入了游戏",
            player_name
        )
        
    async def route_player_quit(self, source_adapter_id: str, player_name: str):
        """转发玩家退出消息到所有其他适配器"""
        logger.debug(f"路由玩家退出: 来源={source_adapter_id}, 玩家={player_name}")
        
        await self._route_message(
            source_adapter_id,
            lambda server_name, player: f"[{server_name}] {player} 离开了游戏",
            player_name
        )
        
    async def route_player_death(self, source_adapter_id: str, death_message: str):
        """转发玩家死亡消息到所有其他适配器"""
        logger.debug(f"路由玩家死亡: 来源={source_adapter_id}, 消息={death_message}")
        
        await self._route_message(
            source_adapter_id,
            lambda server_name, msg: f"[{server_name}] {msg}",
            death_message
        )
        
    async def _broadcast_to_others(self, source_adapter_id: str, message: str, sender: str = None):
        """向除源适配器外的所有适配器广播消息"""
        logger.debug(f"开始广播到其他适配器，排除源: {source_adapter_id}")
        
        tasks = []
        for adapter_id, adapter in self.adapters.items():
            if adapter_id == source_adapter_id:
                logger.debug(f"跳过源适配器: {adapter_id}")
                continue  # 跳过源适配器
                
            if await adapter.is_connected():
                logger.debug(f"向适配器 {adapter_id} ({adapter.server_name}) 发送消息")
                task = adapter.send_rich_message(message)
                tasks.append(task)
        
        # 并发发送消息
        if tasks:
            results = await asyncio.gather(*tasks, return_exceptions=True)
            success_count = 0
            for i, result in enumerate(results):
                if isinstance(result, Exception):
                    logger.error(f"转发消息到适配器时出错: {result}")
                else:
                    success_count += 1

    async def broadcast_message(self, message: str, sender: str = None, images: List[str] = None, exclude_adapter_id: str = None):
        """向所有适配器广播消息（通常用于管理员命令）"""
        tasks = []
        for adapter_id, adapter in self.adapters.items():
            if adapter_id == exclude_adapter_id:
                continue
                
            if await adapter.is_connected():
                task = adapter.send_rich_message(message, hover_text=sender, images=images)
                tasks.append(task)
                
        if tasks:
            await asyncio.gather(*tasks, return_exceptions=True)

    async def save_config(self):
        """保存适配器路由配置到文件"""
        config_file = self.data_dir / "adapter_router_config.json"
        try:
            config = {
                "adapters": list(self.adapters.keys())
            }
            with open(config_file, "w", encoding="utf-8") as f:
                json.dump(config, f, ensure_ascii=False, indent=2)
            logger.info("适配器路由配置已保存")
        except Exception as e:
            logger.error(f"保存适配器路由配置失败: {e}")

    async def close_all_adapters(self):
        """关闭所有适配器"""
        for adapter in self.adapters.values():
            if hasattr(adapter, "close") and callable(adapter.close):
                try:
                    result = adapter.close()
                    if asyncio.iscoroutine(result):
                        await result
                except Exception as e:
                    logger.error(f"关闭适配器 {getattr(adapter, 'adapter_id', str(adapter))} 时出错: {e}")
        logger.info("所有适配器已关闭") 