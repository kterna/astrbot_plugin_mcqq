"""Wiki查询命令处理器"""
from typing import Dict, Any, List, Callable, Awaitable
from astrbot import logger

from ..base_command import BaseCommand
from ...utils.wiki_utils import WikiUtils


class WikiCommand(BaseCommand):
    """处理Wiki查询指令"""
    
    def __init__(self, message_handler):
        super().__init__(prefix="wiki", priority=100)
        self.message_handler = message_handler
    
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
        """执行Wiki查询指令"""
        player_data = data.get("player", {})
        player_name = player_data.get("nickname", player_data.get("display_name", "未知玩家"))
        
        # 获取查询关键词
        wiki_title = self.remove_prefix(message_text)

        try:
            if not wiki_title:
                wiki_data = await WikiUtils.get_random_wiki_content()
            else:
                wiki_data = await WikiUtils.get_wiki_content_by_title(wiki_title)
            
            if wiki_data:
                title = wiki_data["title"]
                content = wiki_data["content"]
                wiki_url = f"https://zh.minecraft.wiki/w/{title}"
                
                if not wiki_title:
                    display_text = f"你知道吗：{title} - {content}"
                else:
                    display_text = f"📖 {title}: {content}"
                
                hover_text = f"🎓 点击查看 {title} 的完整Wiki页面"
                
                if adapter and hasattr(adapter, 'send_rich_message'):
                    await adapter.send_rich_message(display_text, wiki_url, hover_text)
                else:
                    fallback_message = f"{display_text}\n🔗 查看完整页面: {wiki_url}"
                    await send_mc_message_callback(fallback_message)
            else:
                if not wiki_title:
                    await send_mc_message_callback("无法获取随机Wiki内容，请稍后重试")
                else:
                    await send_mc_message_callback(f"无法获取词条 {wiki_title} 的信息，请检查词条名称是否正确")
        except Exception as e:
            logger.error(f"处理Wiki查询时出错: {str(e)}")
            await send_mc_message_callback(f"Wiki查询出错: {str(e)}")
        
        return True
    
    def get_help_text(self) -> str:
        """获取帮助文本"""
        return "<唤醒词>wiki [关键词] - 查询Minecraft Wiki信息，不带关键词则获取随机知识"
