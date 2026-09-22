"""Unit tests for Windows sleep prevention, away mode, and priority tuning."""

import asyncio
import sys
from unittest.mock import MagicMock, patch
import pytest

from app_2_execution_bot.server import prevent_windows_sleep, _windows_keep_alive_loop
from app_2_execution_bot.standalone_bot import prevent_windows_sleep as bot_prevent_sleep


def test_prevent_windows_sleep_execution():
    """Verify prevent_windows_sleep completes without uncaught exception."""
    # Should run gracefully on current platform (Windows or otherwise)
    prevent_windows_sleep()
    bot_prevent_sleep()


def test_prevent_windows_sleep_win32_mock():
    """Verify correct Win32 API flags are passed to kernel32.SetThreadExecutionState."""
    mock_kernel32 = MagicMock()
    mock_kernel32.SetThreadExecutionState.return_value = 0x80000001

    with patch("sys.platform", "win32"), \
         patch("ctypes.windll", MagicMock(kernel32=mock_kernel32), create=True):
        prevent_windows_sleep()

        mock_kernel32.SetThreadExecutionState.assert_called_once()
        args, _ = mock_kernel32.SetThreadExecutionState.call_args
        flags = args[0]
        # Flags must include ES_CONTINUOUS (0x80000000) and ES_SYSTEM_REQUIRED (0x01)
        # ES_AWAYMODE_REQUIRED is excluded so external monitors do not blank out while coding in clamshell mode
        expected_flags = 0x80000000 | 0x00000001
        assert flags == expected_flags


@pytest.mark.asyncio
async def test_windows_keep_alive_loop_cancellation():
    """Verify _windows_keep_alive_loop starts and cleanly cancels without leaking tasks."""
    task = asyncio.create_task(_windows_keep_alive_loop())
    await asyncio.sleep(0.01)
    assert not task.done()
    task.cancel()
    with pytest.raises(asyncio.CancelledError):
        await task
