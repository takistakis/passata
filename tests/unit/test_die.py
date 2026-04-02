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

from unittest.mock import patch

from passata import die


def test_die_calls_notify_on_linux() -> None:
    message = "Test error"
    icon = "dialog-warning"

    with (
        patch("passata.call") as mock_call,
        patch("sys.exit") as mock_exit,
        patch("sys.platform", "linux"),
    ):
        die(message)
        mock_call.assert_called_once_with(
            ["notify-send", "-i", icon, "passata", message],
        )
        mock_exit.assert_called_once_with(1)


def test_die_calls_osascript_on_darwin() -> None:
    """Test that die calls osascript on macOS."""
    message = "Test error"

    with (
        patch("passata.call") as mock_call,
        patch("sys.exit") as mock_exit,
        patch("sys.platform", "darwin"),
    ):
        die(message)
        mock_call.assert_called_once_with(
            [
                "osascript",
                "-e",
                f'display notification "{message}" with title "passata"',
            ],
        )
        mock_exit.assert_called_once_with(1)
