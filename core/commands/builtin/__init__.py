"""内置命令模块"""

from .qq_command import QQCommand
from .help_command import HelpCommand
from .wiki_command import WikiCommand
from .astrbot_command import AstrBotCommand
from .landmark_command import LandmarkCommand

__all__ = [
    'QQCommand',
    'HelpCommand', 
    'WikiCommand',
    'AstrBotCommand',
    'LandmarkCommand'
]
