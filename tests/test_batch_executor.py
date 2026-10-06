"""Unit tests for BatchCommandExecutor."""

import pytest
import asyncio
from core.adapters.batch_executor import BatchCommandExecutor, FailurePolicy


@pytest.mark.asyncio
async def test_batch_executor_all_success():
    async def mock_runner(cmd):
        return f"Executed: {cmd}"

    executor = BatchCommandExecutor(command_runner=mock_runner)
    cmds = ["whitelist on", "whitelist add PlayerA", "say Welcome!"]
    results = await executor.execute_batch(cmds)

    assert len(results) == 3
    assert all(r.success for r in results)
    assert results[0].output == "Executed: whitelist on"


@pytest.mark.asyncio
async def test_batch_executor_abort_policy():
    async def flaky_runner(cmd):
        if "fail" in cmd:
            raise RuntimeError("Connection lost")
        return f"OK: {cmd}"

    executor = BatchCommandExecutor(command_runner=flaky_runner, max_retries=1, retry_delay_sec=0.01)
    cmds = ["cmd1", "fail_cmd", "cmd3"]

    results = await executor.execute_batch(cmds, policy=FailurePolicy.ABORT_ON_ERROR)
    # Should abort after second command
    assert len(results) == 2
    assert results[0].success is True
    assert results[1].success is False
    assert "Connection lost" in results[1].error
