import asyncio
import re
import aiohttp
from typing import Optional, Dict, Any
from astrbot import logger


class WikiUtils:
    """Minecraft Wiki 工具类"""
    
    BASE_API_URL = "https://zh.minecraft.wiki/api.php"
    
    @staticmethod
    async def get_random_wiki_content() -> Optional[Dict[str, str]]:
        """
        从Minecraft Wiki随机获取一个词条
        
        Returns:
            Optional[Dict[str, str]]: 包含title和content的字典，失败时返回None
        """
        api_url = f"{WikiUtils.BASE_API_URL}?action=query&prop=extracts&exintro=true&format=json&generator=random&grnnamespace=0&grnlimit=1"
        
        try:
            data = await WikiUtils._make_wiki_request(api_url)
            if not data:
                return None
            
            # 解析随机词条返回的JSON数据
            pages = data.get("query", {}).get("pages", {})
            if not pages:
                logger.warning("Wiki API返回的数据中没有找到页面")
                return None
            
            # 获取第一个（也是唯一的）页面
            page_id = next(iter(pages.keys()))
            page_data = pages[page_id]
            
            title = page_data.get("title", "未知标题")
            extract = page_data.get("extract", "")
            
            if not extract:
                logger.warning(f"Wiki页面 {title} 没有摘要内容")
                return None
            
            # 清理HTML并格式化内容
            clean_content = WikiUtils._clean_html_and_format(extract, max_length=200)
            
            logger.debug(f"成功获取Wiki词条: {title}")
            return {
                "title": title,
                "content": clean_content
            }
            
        except Exception as e:
            logger.error(f"获取随机Wiki内容时出错: {str(e)}")
            return None
    
    @staticmethod
    async def get_wiki_content_by_title(title: str) -> Optional[Dict[str, str]]:
        """
        根据标题从Minecraft Wiki获取词条内容
        
        Args:
            title: 要搜索的词条标题
            
        Returns:
            Optional[Dict[str, str]]: 包含title和content的字典，失败时返回None
        """
        api_url = f"{WikiUtils.BASE_API_URL}?action=query&prop=extracts&exintro=true&format=json&titles={title}"
        
        try:
            data = await WikiUtils._make_wiki_request(api_url)
            if not data:
                return None
            
            # 解析指定标题返回的JSON数据
            pages = data.get("query", {}).get("pages", {})
            if not pages:
                logger.warning("Wiki API返回的数据中没有找到页面")
                return None
            
            # 获取第一个页面
            page_id = next(iter(pages.keys()))
            page_data = pages[page_id]
            
            # 检查页面是否存在（page_id为-1表示页面不存在）
            if page_id == "-1":
                return None
            
            page_title = page_data.get("title", title)
            extract = page_data.get("extract", "")
            
            if not extract:
                return None
            
            # 清理HTML并格式化内容
            clean_content = WikiUtils._clean_html_and_format(extract, max_length=200)
            
            logger.debug(f"成功获取Wiki词条: {page_title}")
            return {
                "title": page_title,
                "content": clean_content
            }
            
        except Exception as e:
            logger.error(f"获取Wiki内容时出错: {str(e)}")
            return None
    
    @staticmethod
    async def _make_wiki_request(url: str) -> Optional[Dict[str, Any]]:
        """
        发送Wiki API请求
        
        Args:
            url: API请求URL
            
        Returns:
            Optional[Dict[str, Any]]: JSON响应数据，失败时返回None
        """
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(url, timeout=10) as response:
                    if response.status != 200:
                        logger.error(f"Wiki API请求失败，状态码: {response.status}")
                        return None
                    
                    return await response.json()
                    
        except asyncio.TimeoutError:
            logger.error("Wiki API请求超时")
            return None
        except Exception as e:
            logger.error(f"Wiki API请求时出错: {str(e)}")
            return None
    
    @staticmethod
    def _clean_html_and_format(html_text: str, max_length: int = 200) -> str:
        """
        清理HTML标签并格式化文本
        
        Args:
            html_text: 包含HTML标签的文本
            max_length: 最大长度限制
            
        Returns:
            str: 清理后的纯文本
        """
        # 移除HTML标签
        clean_text = re.sub('<[^<]+?>', '', html_text)
        
        # 清理多余的空白字符
        clean_text = re.sub(r'\s+', ' ', clean_text).strip()
        
        # 限制内容长度，避免过长
        if len(clean_text) > max_length:
            clean_text = clean_text[:max_length] + "..."
        
        return clean_text 