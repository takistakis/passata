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

from io import StringIO
from textwrap import dedent

import click
import pytest

import passata
from tests.helpers import run


@pytest.mark.usefixtures("db")
def test_ls_db() -> None:
    result = run(["ls"])

    assert result.output == dedent("""\
        internet
    """)


@pytest.mark.usefixtures("db")
def test_ls_colors_groups() -> None:
    result = run(["--color", "ls"])

    assert result.output == "\x1b[94m\x1b[1minternet\x1b[0m\n"


@pytest.mark.usefixtures("db")
def test_ls_group() -> None:
    result = run(["ls", "internet"])

    assert result.output == dedent("""\
        github
        reddit
    """)


@pytest.mark.usefixtures("db")
def test_ls_nonexistent_group() -> None:
    result = run(["ls", "nonexistent"])

    assert isinstance(result.exception, SystemExit)
    assert result.output == "nonexistent not found\n"


def test_ls_output_preserves_colors_on_a_tty(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    class TTYStringIO(StringIO):
        def isatty(self) -> bool:
            return True

    output = TTYStringIO()
    monkeypatch.setattr(passata.sys, "stdout", output)

    with click.Context(click.Command("test")):
        passata.echo("\x1b[34minternet\x1b[0m")

    assert output.getvalue() == "\x1b[34minternet\x1b[0m\n"


# Tests for nested/filesystem-like paths


@pytest.mark.usefixtures("nested_db")
def test_tree_nested_db() -> None:
    result = run(["tree"])

    assert result.output == dedent("""\
        .
        ├── internet
        │   ├── social
        │   │   ├── reddit
        │   │   └── twitter
        │   └── github
        └── server
    """)


@pytest.mark.usefixtures("nested_db")
def test_tree_nested_group() -> None:
    result = run(["tree", "internet"])

    assert result.output == dedent("""\
        internet
        ├── social
        │   ├── reddit
        │   └── twitter
        └── github
    """)


@pytest.mark.usefixtures("nested_db")
def test_ls_nested_db() -> None:
    result = run(["ls"])

    assert result.output == dedent("""\
        internet
        server
    """)


@pytest.mark.usefixtures("nested_db")
def test_ls_nested_group() -> None:
    result = run(["ls", "internet"])

    assert result.output == dedent("""\
        social
        github
    """)


@pytest.mark.usefixtures("nested_db")
def test_ls_entry_not_group() -> None:
    result = run(["ls", "server"])

    assert isinstance(result.exception, SystemExit)
    assert result.output == "server is an entry, not a group\n"
