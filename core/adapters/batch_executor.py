"""Sequential RCON batch helper with opt-in retry safety."""

import asyncio
import time
from dataclasses import dataclass
from enum import Enum
from typing import Any, Callable, Coroutine, List, Optional


class FailurePolicy(str, Enum):
    CONTINUE_ON_ERROR = "continue"
    ABORT_ON_ERROR = "abort"


@dataclass
class CommandExecutionResult:
    command: str
    success: bool
    output: str
    error: Optional[str] = None
    duration_ms: float = 0.0


class BatchCommandExecutor:
    """Generic helper. The production RconManager batch calls its guarded boundary."""

    def __init__(self, command_runner: Callable[[str], Coroutine[Any, Any, str]],
                 max_retries: int = 0, retry_delay_sec: float = 0.1,
                 retry_safe: Optional[Callable[[str, Exception], bool]] = None):
        if isinstance(max_retries, bool) or not isinstance(max_retries, int) or not 0 <= max_retries <= 3:
            raise ValueError("max_retries must be an integer from 0 to 3")
        if retry_delay_sec < 0:
            raise ValueError("retry_delay_sec must not be negative")
        self.command_runner = command_runner
        self.max_retries = max_retries
        self.retry_delay_sec = retry_delay_sec
        self.retry_safe = retry_safe

    async def execute_batch(self, commands: List[str], policy: FailurePolicy = FailurePolicy.CONTINUE_ON_ERROR) -> List[CommandExecutionResult]:
        results = []
        for cmd in commands:
            start = time.monotonic()
            output = ""
            err_msg = None
            success = False
            for attempt in range(self.max_retries + 1):
                try:
                    output = await self.command_runner(cmd)
                    success = True
                    break
                except asyncio.CancelledError:
                    raise
                except Exception as exc:
                    err_msg = str(exc)
                    if attempt >= self.max_retries or self.retry_safe is None or not self.retry_safe(cmd, exc):
                        break
                    await asyncio.sleep(self.retry_delay_sec)
            results.append(CommandExecutionResult(cmd, success, output if success else "",
                                                  None if success else err_msg,
                                                  round((time.monotonic() - start) * 1000, 2)))
            if not success and policy == FailurePolicy.ABORT_ON_ERROR:
                break
        return results
