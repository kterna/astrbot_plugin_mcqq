"""Message content sanitizer, sensitive regex redactor and anti-spam throttler."""

import re
import time
from typing import Dict, List, Optional, Tuple
from dataclasses import dataclass


@dataclass
class FilterResult:
    allowed: bool
    filtered_text: str
    reason: str = ""
    is_blocked: bool = False


class MessageSanitizer:
    """Sanitizes outgoing Minecraft & QQ messages, masks PII and suppresses spam."""
    PHONE_REGEX = re.compile(r'1[3-9]\d{9}')
    ID_CARD_REGEX = re.compile(r'\d{17}[\dXx]')

    def __init__(self, spam_cooldown_sec: float = 3.0, banned_words: Optional[List[str]] = None):
        self.spam_cooldown_sec = spam_cooldown_sec
        self.banned_words = [w.lower() for w in (banned_words or [])]
        self._user_last_msg: Dict[str, Tuple[str, float]] = {}

    def filter_message(self, user_id: str, text: str) -> FilterResult:
        now = time.monotonic()

        # 1. Anti-spam duplicate check
        if user_id in self._user_last_msg:
            last_text, last_time = self._user_last_msg[user_id]
            if last_text == text and (now - last_time) < self.spam_cooldown_sec:
                return FilterResult(
                    allowed=False,
                    filtered_text="",
                    reason="Duplicate message spam suppressed (P1)",
                    is_blocked=True
                )

        self._user_last_msg[user_id] = (text, now)

        # 2. P0: PII Masking
        clean_text = self.PHONE_REGEX.sub("[PHONE REDACTED]", text)
        clean_text = self.ID_CARD_REGEX.sub("[ID REDACTED]", clean_text)

        # 3. Banned word mask
        for bw in self.banned_words:
            if bw in clean_text.lower():
                pattern = re.compile(re.escape(bw), re.IGNORECASE)
                clean_text = pattern.sub("*" * len(bw), clean_text)

        return FilterResult(allowed=True, filtered_text=clean_text)
