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
from unittest.mock import MagicMock, patch

from passata import call


def test_call_returns_stdout_when_pipe() -> None:
    mock_result = MagicMock()
    mock_result.stdout = "output"
    with patch("subprocess.run", return_value=mock_result) as mock_run:
        out = call(["echo", "hi"], stdout=subprocess.PIPE)
        assert out == "output"
        mock_run.assert_called_once()


def test_call_returns_none_by_default() -> None:
    mock_result = MagicMock()
    mock_result.stdout = None
    with patch("subprocess.run", return_value=mock_result):
        out = call(["echo", "hi"])
        assert out is None


def test_call_passes_input() -> None:
    mock_result = MagicMock()
    with patch("subprocess.run", return_value=mock_result) as mock_run:
        call(["cat"], input_="hello", stdout=subprocess.PIPE)
        _, kwargs = mock_run.call_args
        assert kwargs["input"] == "hello"


def test_call_exits_on_calledprocesserror() -> None:
    with (
        patch("subprocess.run", side_effect=subprocess.CalledProcessError(1, "cmd")),
        patch("sys.exit") as mock_exit,
    ):
        call(["false"])
        mock_exit.assert_called_once()


def test_call_exits_on_filenotfound() -> None:
    with (
        patch("subprocess.run", side_effect=FileNotFoundError),
        patch("sys.exit") as mock_exit,
    ):
        call(["notarealcommand"])
        mock_exit.assert_called_once_with("Executable 'notarealcommand' not found")
