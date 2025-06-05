"""路标命令处理器"""
from typing import Dict, Any, List, Callable, Awaitable
from astrbot import logger
import os
import json

from ..base_command import BaseCommand
from astrbot.core.star.star_tools import StarTools
from ...utils.message_builder import MessageBuilder

class LandmarkCommand(BaseCommand):
    """处理路标相关指令"""
    
    def __init__(self, message_handler=None):
        super().__init__(prefix="路标", priority=100)
        self.message_handler = message_handler

    def _get_landmark_data_path(self, adapter_id: str) -> str:
        # 使用StarTools.get_data_dir获取插件数据目录
        data_dir = StarTools.get_data_dir("mcqq")
        return str(data_dir / f"landmark_{adapter_id}.json")

    def _load_landmarks(self, adapter_id: str) -> Dict[str, Any]:
        path = self._get_landmark_data_path(adapter_id)
        if os.path.exists(path):
            with open(path, "r", encoding="utf-8") as f:
                return json.load(f)
        return {}

    def _save_landmarks(self, adapter_id: str, data: Dict[str, Any]):
        path = self._get_landmark_data_path(adapter_id)
        with open(path, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)

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
        """执行路标指令"""
        player_data = data.get("player", {})
        player_uuid = player_data.get("uuid")
        player_name = player_data.get("nickname", player_data.get("display_name", "未知玩家"))
        player_positon = (player_data.get("block_x"),player_data.get("block_y"),player_data.get("block_z"))
        
        if not player_uuid:
            await send_mc_message_callback("无法获取玩家UUID，无法发送私聊消息")
            return True
        
        adapter_id = getattr(adapter, 'adapter_id', None)
        if not adapter_id:
            await send_mc_message_callback("无法获取适配器ID")
            return True
        
        # 解析指令
        args = message_text[3:].strip().split()
        if not args:
            await send_mc_message_callback("用法: #路标 <查看|增加|删除|编辑> [参数]")
            return True
        action = args[0]
        landmarks = self._load_landmarks(adapter_id)
        
        if action == "查看":
            if not landmarks:
                await send_mc_message_callback("暂无路标信息")
                return True
            components = []
            for name, info in landmarks.items():
                pos = info.get('pos', '')
                desc = info.get('desc', '')
                # 构建带点击传送的组件
                component = MessageBuilder.create_text_event(
                    text=f"{name}: {desc} 坐标: {pos}",
                    color="aqua",
                    bold=False
                )
                MessageBuilder.add_click_event(component, f"/tp {pos}", "SUGGEST_COMMAND")
                MessageBuilder.add_hover_event(component, f"点击传送到 {name}")
                components.append(component)

            await adapter.send_private_message(player_uuid, components)
            return True
        elif action == "增加" and len(args) >= 2:
            name = args[1]
            # 坐标参数优先，否则用player_positon
            if len(args) >= 3:
                pos = args[2]
                desc = " ".join(args[3:]) if len(args) > 3 else ""
            else:
                pos = f"{player_positon[0]} {player_positon[1]} {player_positon[2]}"
                desc = " ".join(args[2:]) if len(args) > 2 else ""
            if name in landmarks:
                await send_mc_message_callback(f"路标 {name} 已存在")
                return True
            landmarks[name] = {"pos": pos, "desc": desc, "creator": player_name}
            self._save_landmarks(adapter_id, landmarks)
            await send_mc_message_callback(f"已增加路标 {name}")
            return True
        elif action == "删除" and len(args) >= 2:
            name = args[1]
            if name not in landmarks:
                await send_mc_message_callback(f"路标 {name} 不存在")
                return True
            del landmarks[name]
            self._save_landmarks(adapter_id, landmarks)
            await send_mc_message_callback(f"已删除路标 {name}")
            return True
        elif action == "编辑" and len(args) >= 2:
            name = args[1]
            if name not in landmarks:
                await send_mc_message_callback(f"路标 {name} 不存在")
                return True
            # 坐标参数优先，否则用player_positon
            if len(args) >= 3:
                pos = args[2]
                desc = " ".join(args[3:]) if len(args) > 3 else landmarks[name].get("desc", "")
            else:
                pos = f"{player_positon[0]} {player_positon[1]} {player_positon[2]}"
                desc = landmarks[name].get("desc", "")
            landmarks[name].update({"pos": pos, "desc": desc})
            self._save_landmarks(adapter_id, landmarks)
            await send_mc_message_callback(f"已编辑路标 {name}")
            return True
        else:
            await send_mc_message_callback("用法: #路标 <查看|增加|删除|编辑> [参数]")
            return True

    def get_help_text(self) -> str:
        return "#路标 <查看|增加|删除|编辑> [参数] - 管理和查询自定义路标" 