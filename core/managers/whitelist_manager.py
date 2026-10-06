"""Dynamic whitelist manager with strict username format validation to prevent command injection."""

import re
from typing import Dict, List, Optional, Set
from dataclasses import dataclass, field
from datetime import datetime


class InvalidPlayerNameError(ValueError):
    """Raised when player name violates Minecraft naming standards."""
    pass


@dataclass
class WhitelistEntry:
    player_name: str
    added_by: str
    added_at: datetime = field(default_factory=datetime.utcnow)


class WhitelistManager:
    """Manages player whitelists across Minecraft server instances with command-injection safeguards."""

    # P0: Strict alphanumeric + underscore, 3-16 chars standard
    NAME_REGEX = re.compile(r'^[a-zA-Z0-9_]{3,16}$')

    def __init__(self):
        self._whitelists: Dict[str, Dict[str, WhitelistEntry]] = {}

    @classmethod
    def validate_name(cls, player_name: str) -> str:
        clean = player_name.strip()
        if not cls.NAME_REGEX.match(clean):
            raise InvalidPlayerNameError(
                f"Invalid player name '{player_name}'. Must match ^[a-zA-Z0-9_]{{3,16}}$ to prevent injection."
            )
        return clean

    def add_player(self, server_name: str, player_name: str, operator: str = "system") -> bool:
        clean_name = self.validate_name(player_name)
        if server_name not in self._whitelists:
            self._whitelists[server_name] = {}

        if clean_name.lower() in self._whitelists[server_name]:
            return False # Idempotent: already exists

        self._whitelists[server_name][clean_name.lower()] = WhitelistEntry(
            player_name=clean_name,
            added_by=operator
        )
        return True

    def remove_player(self, server_name: str, player_name: str) -> bool:
        clean_name = self.validate_name(player_name)
        if server_name not in self._whitelists:
            return False
        return self._whitelists[server_name].pop(clean_name.lower(), None) is not None

    def is_whitelisted(self, server_name: str, player_name: str) -> bool:
        try:
            clean_name = self.validate_name(player_name)
        except InvalidPlayerNameError:
            return False
        srv_list = self._whitelists.get(server_name, {})
        return clean_name.lower() in srv_list

    def list_players(self, server_name: str) -> List[str]:
        srv_list = self._whitelists.get(server_name, {})
        return [entry.player_name for entry in srv_list.values()]
