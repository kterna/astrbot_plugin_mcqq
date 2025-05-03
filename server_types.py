class Vanilla():
    def __init__(self):
        self.server_type="vanilla"
        self.chat="MinecraftPlayerChatEvent"
        self.join="MinecraftPlayerJoinEvent"
        self.quit="MinecraftPlayerQuitEvent"

        self.player={
            "nickname": "nickname",
        }

class Spigot():
    def __init__(self):
        self.server_type="spigot"
        self.chat="AsyncPlayerChatEvent"
        self.join="PlayerJoinEvent"
        self.quit="PlayerQuitEvent"
        self.death="PlayerDeathEvent"
        self.player_command="PlayerCommandPreprocessEvent"

        self.player={
            "nickname": "nickname",
        }

class Fabric():
    def __init__(self):
        self.server_type="fabric"
        self.chat="ServerMessageEvent"
        self.join="ServerPlayConnectionJoinEvent"
        self.quit="ServerPlayConnectionDisconnectEvent"
        self.death="ServerLivingEntityAfterDeathEvent"
        self.player_command="ServerCommandMessageEvent"

        self.player={
            "nickname": "nickname",
            "block_x": "block_x",
            "block_y": "block_y",
            "block_z": "block_z",
        }

class Forge():    
    def __init__(self):
        self.server_type="forge"
        self.chat="ServerChatEvent"
        self.join="PlayerLoggedInEvent"
        self.quit="PlayerLoggedOutEvent"

        self.player={
            "nickname": "nickname",
            "block_x": "block_x",
            "block_y": "block_y",
            "block_z": "block_z",
        }
    
class Neoforge():
    def __init__(self):
        self.server_type="neoforge"
        self.chat="NeoServerChatEvent"
        self.join="NeoPlayerLoggedInEvent"
        self.quit="NeoPlayerLoggedOutEvent"
        self.player_command="NeoCommandEventb"

        self.player={
            "nickname": "nickname",
            "block_x": "block_x",
            "block_y": "block_y",
            "block_z": "block_z",
        }
