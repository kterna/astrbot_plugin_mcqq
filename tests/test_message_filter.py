"""Unit tests for MessageSanitizer."""

import pytest
import time
from core.routing.message_filter import MessageSanitizer


def test_pii_masking():
    sanitizer = MessageSanitizer(banned_words=["griefing"])
    res = sanitizer.filter_message("u1", "Call me at 13800138000 tomorrow!")
    assert res.allowed is True
    assert "[PHONE REDACTED]" in res.filtered_text

    # Banned words
    res2 = sanitizer.filter_message("u2", "Server griefing is bad")
    assert res2.allowed is True
    assert "********" in res2.filtered_text


def test_spam_suppression():
    sanitizer = MessageSanitizer(spam_cooldown_sec=1.0)
    assert sanitizer.filter_message("u1", "spam text").allowed is True
    # Immediate duplicate
    assert sanitizer.filter_message("u1", "spam text").allowed is False
