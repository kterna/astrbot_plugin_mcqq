from typing import Dict


class Vanilla:
    """Vanilla Minecraft 服务器事件配置"""
    
    def __init__(self) -> None:
        self.server_type: str = "vanilla"
        self.chat: str = "MinecraftPlayerChatEvent"
        self.join: str = "MinecraftPlayerJoinEvent"
        self.quit: str = "MinecraftPlayerQuitEvent"

        self.player: Dict[str, str] = {
            "nickname": "nickname",
        }


class Spigot:
    """Spigot/Paper Minecraft 服务器事件配置"""
    
    def __init__(self) -> None:
        self.server_type: str = "spigot"
        self.chat: str = "AsyncPlayerChatEvent"
        self.join: str = "PlayerJoinEvent"
        self.quit: str = "PlayerQuitEvent"
        self.death: str = "PlayerDeathEvent"
        self.player_command: str = "PlayerCommandPreprocessEvent"

        self.player: Dict[str, str] = {
            "nickname": "nickname",
        }


class Fabric:
    """Fabric Minecraft 服务器事件配置"""
    
    def __init__(self) -> None:
        self.server_type: str = "fabric"
        self.chat: str = "ServerMessageEvent"
        self.join: str = "ServerPlayConnectionJoinEvent"
        self.quit: str = "ServerPlayConnectionDisconnectEvent"
        self.death: str = "ServerLivingEntityAfterDeathEvent"
        self.player_command: str = "ServerCommandMessageEvent"

        self.player: Dict[str, str] = {
            "nickname": "nickname",
            "block_x": "block_x",
            "block_y": "block_y",
            "block_z": "block_z",
        }


class Forge:
    """Forge Minecraft 服务器事件配置"""
    
    def __init__(self) -> None:
        self.server_type: str = "forge"
        self.chat: str = "ServerChatEvent"
        self.join: str = "PlayerLoggedInEvent"
        self.quit: str = "PlayerLoggedOutEvent"

        self.player: Dict[str, str] = {
            "nickname": "nickname",
            "block_x": "block_x",
            "block_y": "block_y",
            "block_z": "block_z",
        }
    

class Neoforge:
    """Neoforge Minecraft 服务器事件配置"""
    
    def __init__(self) -> None:
        self.server_type: str = "neoforge"
        self.chat: str = "NeoServerChatEvent"
        self.join: str = "NeoPlayerLoggedInEvent"
        self.quit: str = "NeoPlayerLoggedOutEvent"
        self.player_command: str = "NeoCommandEvent"

        self.player: Dict[str, str] = {
            "nickname": "nickname",
            "block_x": "block_x",
            "block_y": "block_y",
            "block_z": "block_z",
        }


class McdrServer:
    """MCDR (MCDReforged) 服务器事件配置"""
    
    def __init__(self) -> None:
        self.server_type: str = "mcdr"
        self.chat: str = "MCDRChat"
        self.join: str = "MCDRJoin"
        self.quit: str = "MCDRQuit"
        self.death: str = "MCDRDeath"
        self.player_command: str = "MCDRPlayer_command"

        self.player: Dict[str, str] = {
            "nickname": "nickname",
            "uuid": "uuid",
            "is_op": "is_op",
            "dimension": "dimension",
            "coordinate": "coordinate",
        }


class QueqiaoV2:
    """Queqiao V2 Minecraft 服务器事件配置"""
    # 原版端 仅支持 nickname
    # Spigot：不支持 max_health
    # Paper：不支持 max_health
    # Folia：
    #   不支持 max_health
    #   可能缺失 address
    # Velocity 仅支持 nickname、uuid、is_op
    # Forge
    #   1.7.10：缺少 address
    
    def __init__(self) -> None:
        self.server_type: str = "" # Queqiao V2 服务器类型不区分具体类型
        self.chat: str = "PlayerChatEvent"
        self.join: str = "PlayerJoinEvent"
        self.quit: str = "PlayerQuitEvent"
        self.death: str = "PlayerDeathEvent"
        self.player_command: str = "PlayerCommandEvent"
        self.achievent: str = "PlayerAchievementEvent"
        
        self.player: Dict[str, str] = {
            "nickname": "nickname",
            "uuid": "uuid",
            "is_op": "is_op",
            "dimension": "dimension",
            "coordinate": "coordinate",
            "health": "health", # 当前生命值
            "max_health": "max_health", # 最大生命值
            "experience_level": "experience_level", # 经验等级
            "experience_progress": "experience_progress", # 当前经验进度（0.0-1.0）
            "total_experience": "total_experience", # 总经验值
            "walk_speed": "walk_speed",
            "block_x": "x",
            "block_y": "y",
            "block_z": "z",
        }