"""Configuration schema migration engine from v1 to v2 with safety backups."""

import copy
import json
from typing import Dict, Any, Tuple


class ConfigMigrationEngine:
    """Migrates legacy configurations to modern standard with safety backup verification."""

    @staticmethod
    def migrate_v1_to_v2(old_config: Dict[str, Any]) -> Tuple[Dict[str, Any], Dict[str, Any]]:
        """
        Takes old config, generates a backup copy (P0), and outputs migrated v2 config.
        """
        backup_copy = copy.deepcopy(old_config)
        new_config = {
            "version": "v2.0",
            "server": {
                "name": old_config.get("server_name", "minecraft_default"),
                "host": old_config.get("host", "127.0.0.1"),
                "port": old_config.get("port", 25575),
            },
            "security": {
                "rcon_password": old_config.get("password", ""),
                "rate_limit": old_config.get("rate_limit", 5.0),
                "enable_guard": True
            },
            "forwarding": {
                "group_ids": old_config.get("groups", []),
                "broadcast_join_leave": old_config.get("notify_players", True)
            }
        }
        return new_config, backup_copy
