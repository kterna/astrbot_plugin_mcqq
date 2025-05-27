"""内置命令模块"""

from .qq_command import QQCommand
from .help_command import HelpCommand
from .restart_command import RestartCommand
from .wiki_command import WikiCommand
from .astrbot_command import AstrBotCommand

__all__ = [
    'QQCommand',
    'HelpCommand', 
    'RestartCommand',
    'WikiCommand',
    'AstrBotCommand'
]
