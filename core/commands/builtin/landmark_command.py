"""路标命令处理器"""
from typing import Dict, Any, List, Callable, Awaitable, Optional, Tuple
from dataclasses import dataclass
from astrbot import logger
import os
import json

from ..base_command import BaseCommand
from astrbot.core.star.star_tools import StarTools
from ...utils.message_builder import MessageBuilder


@dataclass
class LandmarkArgs:
    """路标命令参数数据类"""
    action: str
    name: Optional[str] = None
    position: Optional[str] = None
    description: Optional[str] = None
    use_player_position: bool = False


class LandmarkCommand(BaseCommand):
    """处理路标相关指令"""
    
    def __init__(self, message_handler=None):
        super().__init__(prefix="路标", priority=100)
        self.message_handler = message_handler

    def _get_landmark_data_path(self, adapter_id: str) -> str:
        """获取地标数据文件路径"""
        data_dir = StarTools.get_data_dir("mcqq")
        return str(data_dir / f"landmark_{adapter_id}.json")

    def _load_landmarks(self, adapter_id: str) -> Dict[str, Any]:
        """加载地标数据"""
        path = self._get_landmark_data_path(adapter_id)
        if os.path.exists(path):
            try:
                with open(path, "r", encoding="utf-8") as f:
                    return json.load(f)
            except (json.JSONDecodeError, IOError) as e:
                logger.error(f"加载地标数据失败: {e}")
                return {}
        return {}

    def _save_landmarks(self, adapter_id: str, data: Dict[str, Any]) -> bool:
        """保存地标数据"""
        try:
            path = self._get_landmark_data_path(adapter_id)
            with open(path, "w", encoding="utf-8") as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
            return True
        except (IOError, TypeError) as e:
            logger.error(f"保存地标数据失败: {e}")
            return False

    def _parse_arguments(self, message_text: str) -> LandmarkArgs:
        """解析路标命令参数"""
        # 去掉命令前缀并分割参数
        args = self.remove_prefix(message_text).split()
        
        if not args:
            raise ValueError("请提供操作类型")
        
        action = args[0]
        
        if action == "查看":
            return LandmarkArgs(action=action)
        
        elif action in ["增加", "编辑"]:
            if len(args) < 2:
                raise ValueError(f"{action}操作需要提供路标名称")
            
            name = args[1]
            
            # 解析坐标和描述
            if len(args) >= 3 and self._is_coordinate_format(args[2]):
                # 格式: #路标 增加 名称 "x y z" 描述
                position = args[2]
                description = " ".join(args[3:]) if len(args) > 3 else ""
                use_player_position = False
            else:
                # 格式: #路标 增加 名称 描述 (使用玩家当前位置)
                position = None
                description = " ".join(args[2:]) if len(args) > 2 else ""
                use_player_position = True
            
            return LandmarkArgs(
                action=action,
                name=name,
                position=position,
                description=description,
                use_player_position=use_player_position
            )
        
        elif action == "删除":
            if len(args) < 2:
                raise ValueError("删除操作需要提供路标名称")
            return LandmarkArgs(action=action, name=args[1])
        
        else:
            raise ValueError(f"未知操作类型: {action}")

    def _is_coordinate_format(self, text: str) -> bool:
        """检查文本是否为坐标格式 (x y z)"""
        try:
            parts = text.split()
            if len(parts) != 3:
                return False
            # 尝试转换为整数
            for part in parts:
                int(part)
            return True
        except ValueError:
            return False

    def _validate_coordinates(self, coords: str) -> Tuple[bool, str]:
        """验证坐标格式和范围"""
        try:
            parts = coords.split()
            if len(parts) != 3:
                return False, "坐标格式错误，应为: x y z"
            
            x, y, z = map(int, parts)
            
            # Minecraft坐标范围验证
            if not (-30000000 <= x <= 30000000):
                return False, f"X坐标超出范围: {x} (应在-30000000到30000000之间)"
            if not (-2048 <= y <= 2048):
                return False, f"Y坐标超出范围: {y} (应在-2048到2048之间)"
            if not (-30000000 <= z <= 30000000):
                return False, f"Z坐标超出范围: {z} (应在-30000000到30000000之间)"
            
            return True, ""
        except ValueError:
            return False, "坐标必须为整数"

    def _format_player_position(self, player_position: Tuple) -> str:
        """格式化玩家位置"""
        x, y, z = player_position
        if None in (x, y, z):
            raise ValueError("无法获取玩家坐标")
        return f"{x} {y} {z}"

    async def _handle_view_landmarks(self, adapter, player_uuid: str, landmarks: Dict[str, Any]) -> bool:
        """处理查看路标操作"""
        if not landmarks:
            await adapter.send_private_message(player_uuid, [MessageBuilder.create_text_event(
                "暂无路标信息", color="yellow"
            )])
            return True

        components = []
        for name, info in landmarks.items():
            pos = info.get('pos', '')
            desc = info.get('desc', '')
            creator = info.get('creator', '未知')
            
            # 构建带点击传送的组件
            component = MessageBuilder.create_text_event(
                text=f"{name}: {desc} 坐标: {pos} (创建者: {creator})",
                color="aqua",
                bold=False
            )
            MessageBuilder.add_click_event(component, f"/tp {pos}", "SUGGEST_COMMAND")
            MessageBuilder.add_hover_event(component, f"点击传送到 {name}")
            components.append(component)

        await adapter.send_private_message(player_uuid, components)
        return True

    async def _handle_add_or_edit_landmark(self, args: LandmarkArgs, landmarks: Dict[str, Any], 
                                         player_data: Dict[str, Any], adapter_id: str,
                                         send_mc_message_callback: Callable[[str], Awaitable[None]]) -> bool:
        """统一处理增加和编辑路标操作"""
        name = args.name
        player_name = player_data.get("nickname", player_data.get("display_name", "未知玩家"))
        
        # 检查路标是否存在
        landmark_exists = name in landmarks
        
        if args.action == "增加" and landmark_exists:
            await send_mc_message_callback(f"路标 {name} 已存在")
            return True
        
        if args.action == "编辑" and not landmark_exists:
            await send_mc_message_callback(f"路标 {name} 不存在")
            return True
        
        # 确定坐标
        if args.use_player_position:
            try:
                player_position = (
                    player_data.get("block_x"),
                    player_data.get("block_y"),
                    player_data.get("block_z")
                )
                position = self._format_player_position(player_position)
            except ValueError as e:
                await send_mc_message_callback(f"❌ {str(e)}")
                return True
        else:
            position = args.position
        
        # 验证坐标
        is_valid, error_msg = self._validate_coordinates(position)
        if not is_valid:
            await send_mc_message_callback(f"❌ {error_msg}")
            return True
        
        # 处理描述
        description = args.description or ""
        if args.action == "编辑" and not args.description:
            # 编辑时如果没有提供新描述，保留原描述
            description = landmarks[name].get("desc", "")
        
        # 保存或更新路标
        landmark_data = {
            "pos": position,
            "desc": description,
            "creator": player_name
        }
        
        if args.action == "编辑":
            # 编辑时保留原创建者
            landmark_data["creator"] = landmarks[name].get("creator", player_name)
        
        landmarks[name] = landmark_data
        
        if self._save_landmarks(adapter_id, landmarks):
            action_text = "增加" if args.action == "增加" else "编辑"
            await send_mc_message_callback(f"✅ 已{action_text}路标 {name}")
        else:
            await send_mc_message_callback(f"❌ {args.action}路标失败，请稍后重试")
        
        return True

    async def _handle_delete_landmark(self, name: str, landmarks: Dict[str, Any], adapter_id: str,
                                    send_mc_message_callback: Callable[[str], Awaitable[None]]) -> bool:
        """处理删除路标操作"""
        if name not in landmarks:
            await send_mc_message_callback(f"路标 {name} 不存在")
            return True
        
        del landmarks[name]
        
        if self._save_landmarks(adapter_id, landmarks):
            await send_mc_message_callback(f"✅ 已删除路标 {name}")
        else:
            await send_mc_message_callback("❌ 删除路标失败，请稍后重试")
        
        return True

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
        
        if not player_uuid:
            await send_mc_message_callback("无法获取玩家UUID，无法执行路标操作")
            return True
        
        adapter_id = getattr(adapter, 'adapter_id', None)
        if not adapter_id:
            await send_mc_message_callback("无法获取适配器ID")
            return True
        
        try:
            # 解析命令参数
            args = self._parse_arguments(message_text)
        except ValueError as e:
            await send_mc_message_callback(f"❌ 参数错误: {str(e)}")
            await send_mc_message_callback("用法: #路标 <查看|增加|删除|编辑> [参数]")
            return True
        
        # 加载地标数据
        landmarks = self._load_landmarks(adapter_id)
        
        # 根据操作类型执行相应处理
        try:
            if args.action == "查看":
                return await self._handle_view_landmarks(adapter, player_uuid, landmarks)
            
            elif args.action in ["增加", "编辑"]:
                return await self._handle_add_or_edit_landmark(
                    args, landmarks, player_data, adapter_id, send_mc_message_callback
                )
            
            elif args.action == "删除":
                return await self._handle_delete_landmark(
                    args.name, landmarks, adapter_id, send_mc_message_callback
                )
            
        except Exception as e:
            logger.error(f"执行路标操作时出错: {str(e)}")
            await send_mc_message_callback(f"❌ 操作失败: {str(e)}")
        
        return True

    def get_help_text(self) -> str:
        """获取帮助文本"""
        return """#路标 <操作> [参数] - 管理和查询自定义路标
操作类型:
  查看 - 显示所有路标
  增加 <名称> [坐标] [描述] - 增加新路标
  编辑 <名称> [坐标] [描述] - 编辑现有路标  
  删除 <名称> - 删除路标
注意: 坐标格式为 "x y z"，不提供坐标则使用当前位置""" 
