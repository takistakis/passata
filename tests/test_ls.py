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

"""Tests for passata ls."""

from pathlib import Path
from textwrap import dedent

from tests.helpers import run


def test_ls_db(db: Path) -> None:
    result = run(["ls"])
    assert result.output == dedent(
        """\
        internet
        ├── github
        └── reddit
        """
    )


def test_ls_group(db: Path) -> None:
    result = run(["ls", "internet"])
    assert result.output == dedent(
        """\
        github
        reddit
        """
    )


def test_ls_no_tree(db: Path) -> None:
    result = run(["ls", "--no-tree"])
    assert result.output == dedent(
        """\
        internet/github
        internet/reddit
        """
    )


def test_ls_nonexistent_group(db: Path) -> None:
    result = run(["ls", "nonexistent"])
    assert isinstance(result.exception, SystemExit)
    assert result.output == "nonexistent not found\n"
