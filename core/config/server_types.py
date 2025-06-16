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
