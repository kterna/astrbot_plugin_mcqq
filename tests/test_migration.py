"""Unit tests for ConfigMigrationEngine."""

import pytest
from core.config.migration import ConfigMigrationEngine


def test_config_migration():
    v1 = {
        "server_name": "MySurvival",
        "host": "192.168.1.50",
        "port": 25575,
        "password": "secret_password",
        "groups": [12345678, 87654321]
    }
    v2, backup = ConfigMigrationEngine.migrate_v1_to_v2(v1)
    assert v2["version"] == "v2.0"
    assert v2["server"]["name"] == "MySurvival"
    assert v2["security"]["rcon_password"] == "secret_password"
    assert backup == v1
