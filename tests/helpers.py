# Copyright 2017 Panagiotis Ktistakis <panktist@gmail.com>
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

"""Helper functions for the passata test suite."""

from collections.abc import Sequence
from pathlib import Path
from unittest.mock import patch

from click.testing import CliRunner, Result

import passata

_clipboard_content = [""]
_to_clipboard = passata.to_clipboard


def read(dbpath: Path) -> str:
    return dbpath.open().read()


def run(args: Sequence[str], input_: str | None = None) -> Result:
    _clipboard_content[0] = ""
    runner = CliRunner()

    if passata.to_clipboard is _to_clipboard:

        def capture_clipboard(data: str, timeout: int) -> None:
            del timeout
            _clipboard_content[0] = data

        with patch.object(passata, "to_clipboard", capture_clipboard):
            return runner.invoke(passata.cli, args, input_)

    return runner.invoke(passata.cli, args, input_)


def clipboard() -> str:
    return _clipboard_content[0]
