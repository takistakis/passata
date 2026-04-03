import subprocess
from unittest.mock import patch

from passata import schedule_clear_clipboard


def test_schedule_clear_clipboard_spawns_detached_process() -> None:
    """schedule_clear_clipboard should launch a detached background process."""
    with patch("subprocess.Popen") as mock_popen:
        schedule_clear_clipboard(10)
        mock_popen.assert_called_once()
        args, kwargs = mock_popen.call_args
        assert args[0] == ["/bin/sh", "-c", "sleep 10 && printf '' | pbcopy"]
        assert kwargs["start_new_session"] is True
        assert kwargs["stdout"] == subprocess.DEVNULL
        assert kwargs["stderr"] == subprocess.DEVNULL
