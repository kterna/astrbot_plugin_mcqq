"""Unit tests for WhitelistManager."""

import pytest
from core.managers.whitelist_manager import WhitelistManager, InvalidPlayerNameError


def test_whitelist_validation():
    wm = WhitelistManager()

    # Valid names
    assert wm.validate_name("Alex") == "Alex"
    assert wm.validate_name("Steve_123") == "Steve_123"

    # Invalid names (Injection attempts or illegal chars)
    with pytest.raises(InvalidPlayerNameError):
        wm.validate_name("Notch; op hacker")

    with pytest.raises(InvalidPlayerNameError):
        wm.validate_name("ab") # Too short

    with pytest.raises(InvalidPlayerNameError):
        wm.validate_name("this_name_is_way_too_long_for_minecraft")


def test_whitelist_crud_and_idempotency():
    wm = WhitelistManager()
    srv = "survival"

    # Add
    assert wm.add_player(srv, "PlayerOne", operator="Admin") is True
    # Duplicate add returns False (idempotent)
    assert wm.add_player(srv, "playerone", operator="Admin") is False

    # Check
    assert wm.is_whitelisted(srv, "PlayerOne") is True
    assert wm.is_whitelisted(srv, "UnknownPlayer") is False

    # List
    players = wm.list_players(srv)
    assert "PlayerOne" in players

    # Remove
    assert wm.remove_player(srv, "PlayerOne") is True
    assert wm.remove_player(srv, "PlayerOne") is False
    assert wm.is_whitelisted(srv, "PlayerOne") is False
