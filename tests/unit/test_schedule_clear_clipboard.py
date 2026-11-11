# Copyright 2026 Panagiotis Ktistakis <panktist@gmail.com>
#
# This file is part of passata.
#
# passata is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# passata is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with passata.  If not, see <http://www.gnu.org/licenses/>.

import subprocess
from unittest.mock import patch

import pytest

import passata
from passata import schedule_clear_clipboard


@pytest.mark.parametrize(
    ("platform", "display", "session", "clear"),
    [
        ("darwin", "", "", "pbcopy"),
        ("linux", "wayland-1", "wayland", "wl-copy --clear"),
        ("linux", "", "x11", "xsel -c -b"),
    ],
)
def test_schedule_clear_clipboard_spawns_detached_process(
    monkeypatch: pytest.MonkeyPatch,
    platform: str,
    display: str,
    session: str,
    clear: str,
) -> None:
    """schedule_clear_clipboard should launch a detached background process."""
    monkeypatch.setattr(passata.sys, "platform", platform)
    monkeypatch.setenv("WAYLAND_DISPLAY", display)
    monkeypatch.setenv("XDG_SESSION_TYPE", session)
    with patch("subprocess.Popen") as mock_popen:
        schedule_clear_clipboard(10)
        mock_popen.assert_called_once()
        args, kwargs = mock_popen.call_args
        assert args[0] == ["/bin/sh", "-c", f"sleep 10 && printf '' | {clear}"]
        assert kwargs["start_new_session"] is True
        assert kwargs["stdout"] == subprocess.DEVNULL
        assert "stderr" not in kwargs


@pytest.mark.parametrize("timeout", [0, 10])
@pytest.mark.parametrize(
    ("platform", "display", "session", "program"),
    [
        ("linux", "", "x11", "xsel"),
        ("linux", "", "", "xsel"),
        ("linux", "wayland-1", "wayland", "wl-copy"),
        ("linux", "wayland-1", "x11", "wl-copy"),
        ("linux", "", "wayland", "wl-copy"),
        ("darwin", "wayland-1", "wayland", "pbcopy"),
    ],
)
def test_clipboard_backend_and_timeout(
    monkeypatch: pytest.MonkeyPatch,
    platform: str,
    display: str,
    session: str,
    program: str,
    timeout: int,
) -> None:
    monkeypatch.setattr(passata.sys, "platform", platform)
    monkeypatch.setenv("WAYLAND_DISPLAY", display)
    monkeypatch.setenv("XDG_SESSION_TYPE", session)
    monkeypatch.setenv("DISPLAY", ":1")
    command = [program]
    if program == "xsel":
        command.extend(["-i", "-b"])
    with (
        patch.object(passata, "call") as call,
        patch.object(passata, "schedule_clear_clipboard") as clear,
    ):
        passata.to_clipboard("password\nwith 'quotes'", timeout)
        call.assert_called_once_with(command, input_="password\nwith 'quotes'")
        if timeout:
            clear.assert_called_once_with(timeout)
        else:
            clear.assert_not_called()


def test_failed_copy_does_not_schedule_clear(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(passata.sys, "platform", "linux")
    monkeypatch.setenv("WAYLAND_DISPLAY", "wayland-1")
    with (
        patch.object(passata, "call", side_effect=SystemExit("wl-copy failed")),
        patch.object(passata, "schedule_clear_clipboard") as clear,
        pytest.raises(SystemExit, match="wl-copy failed"),
    ):
        passata.to_clipboard("password", 10)
    clear.assert_not_called()
