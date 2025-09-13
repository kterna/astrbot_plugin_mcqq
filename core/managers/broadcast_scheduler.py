import asyncio
import datetime
from typing import Callable, Optional, List, Any

from astrbot import logger

from .broadcast_config import BroadcastConfigManager
from ..utils.wiki_utils import WikiUtils


class BroadcastScheduler:
    """调度和执行整点广播"""

    def __init__(self, plugin_instance, config_manager: BroadcastConfigManager, broadcast_callback: Callable):
        """
        初始化调度器。

        Args:
            plugin_instance: MCQQPlugin 实例。
            config_manager (BroadcastConfigManager): 配置管理器实例。
            broadcast_callback (Callable): 发送广播时要调用的回调函数。
        """
        self.plugin = plugin_instance
        self.config_manager = config_manager
        self.broadcast_callback = broadcast_callback
        self.hourly_broadcast_task: Optional[asyncio.Task] = None

    def start(self):
        """启动整点广播的后台任务"""
        if self.hourly_broadcast_task and not self.hourly_broadcast_task.done():
            logger.warning("广播任务已在运行中")
            return
        self.hourly_broadcast_task = asyncio.create_task(self._hourly_broadcast_loop())
        

    def stop(self):
        """停止整点广播任务"""
        if self.hourly_broadcast_task and not self.hourly_broadcast_task.done():
            self.hourly_broadcast_task.cancel()
            logger.info("已取消整点广播任务")

    async def _hourly_broadcast_loop(self):
        """整点广播的循环逻辑"""
        logger.info("启动整点广播任务")
        while True:
            now = datetime.datetime.now()
            next_hour = now.replace(minute=0, second=0, microsecond=0) + datetime.timedelta(hours=1)
            sleep_time = (next_hour - now).total_seconds()
            
            logger.debug(f"下一次整点广播将在 {sleep_time:.2f} 秒后")
            await asyncio.sleep(sleep_time)

            # 获取所有适配器并执行广播
            adapters = await self.plugin.get_all_minecraft_adapter()
            await self.execute_hourly_broadcast(adapters)

    async def execute_hourly_broadcast(self, adapters: List[Any]):
        """执行一次完整的整点广播（包括Wiki）"""
        if not self.config_manager.is_enabled():
            logger.info("整点广播已关闭，跳过广播")
            return

        # 为每个适配器广播其特定的内容
        for adapter in adapters:
            content = self.config_manager.get_broadcast_content(adapter.adapter_id)
            success = await self.broadcast_callback([adapter], content)
            if success:
                logger.info(f"向适配器 {adapter.adapter_id} 的整点广播已成功执行")
            else:
                logger.warning(f"向适配器 {adapter.adapter_id} 的整点广播执行失败")

        # 广播Wiki内容
        try:
            wiki_content = await WikiUtils.get_wiki_broadcast_content()
            if wiki_content:
                await asyncio.sleep(0.1)  # 短暂延迟，避免消息刷屏
                await self.broadcast_callback(adapters, wiki_content)
            else:
                logger.warning("获取Wiki随机内容失败，跳过Wiki广播")
        except Exception as e:
            logger.error(f"Wiki广播执行时出错: {str(e)}") 