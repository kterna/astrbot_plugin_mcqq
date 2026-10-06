"""Batch command executor for atomic/sequential RCON operations with retry policy."""

import asyncio
import time
from enum import Enum
from typing import Any, Callable, Coroutine, Dict, List, Optional
from dataclasses import dataclass


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
    """Executes a list of RCON commands sequentially with configurable error policy and retry logic."""

    def __init__(
        self,
        command_runner: Callable[[str], Coroutine[Any, Any, str]],
        max_retries: int = 2,
        retry_delay_sec: float = 0.1
    ):
        self.command_runner = command_runner
        self.max_retries = max_retries
        self.retry_delay_sec = retry_delay_sec

    async def execute_batch(
        self,
        commands: List[str],
        policy: FailurePolicy = FailurePolicy.CONTINUE_ON_ERROR
    ) -> List[CommandExecutionResult]:
        results: List[CommandExecutionResult] = []

        for cmd in commands:
            start = time.monotonic()
            success = False
            output = ""
            err_msg = None

            for attempt in range(self.max_retries + 1):
                try:
                    output = await self.command_runner(cmd)
                    success = True
                    break
                except Exception as e:
                    err_msg = str(e)
                    if attempt < self.max_retries:
                        await asyncio.sleep(self.retry_delay_sec)

            dur = (time.monotonic() - start) * 1000.0
            res = CommandExecutionResult(
                command=cmd,
                success=success,
                output=output if success else "",
                error=err_msg if not success else None,
                duration_ms=round(dur, 2)
            )
            results.append(res)

            if not success and policy == FailurePolicy.ABORT_ON_ERROR:
                break

        return results
