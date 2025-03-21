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

import sys
import time
from pathlib import Path
from typing import Sequence

from click.testing import CliRunner, Result

import passata


def read(dbpath: Path) -> str:
    return dbpath.open().read()


def run(args: Sequence[str], input: str | None = None) -> Result:
    runner = CliRunner()
    return runner.invoke(passata.cli, args, input)


def clipboard() -> str:
    command = ["pbpaste"] if sys.platform == "darwin" else ["xsel", "-o", "-b"]
    time.sleep(0.1)
    return passata.out(command)
