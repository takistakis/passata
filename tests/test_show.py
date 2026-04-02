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

"""Tests for passata show."""

from collections.abc import Callable
from textwrap import dedent

import pytest

from tests.helpers import clipboard, run


@pytest.mark.usefixtures("db")
def test_show() -> None:
    result = run(["show", "internet/github"])
    assert result.output == dedent("""\
        password: gh
        username: takis
    """)


@pytest.mark.usefixtures("db")
def test_show_nonexistent_entry() -> None:
    result = run(["show", "internet/nonexistent"])
    assert isinstance(result.exception, SystemExit)
    assert result.output == "internet/nonexistent not found\n"


@pytest.mark.usefixtures("db")
def test_show_entry_three_levels_deep() -> None:
    result = run(["show", "one/two/three"])
    assert isinstance(result.exception, SystemExit)
    assert result.output == "one/two/three is nested too deeply\n"


@pytest.mark.usefixtures("db")
def test_show_clipboard() -> None:
    result = run(["show", "internet/github", "--clip"])
    assert result.output == ""
    assert clipboard() == "gh"


@pytest.mark.usefixtures("db")
def test_show_clipboard_whole_database() -> None:
    result = run(["show", "--clip"])
    assert isinstance(result.exception, SystemExit)
    assert result.output == "Can't put the entire database to clipboard\n"


@pytest.mark.usefixtures("db")
def test_show_clipboard_whole_group() -> None:
    result = run(["show", "internet", "--clip"])
    assert isinstance(result.exception, SystemExit)
    assert result.output == "Can't put the entire group to clipboard\n"


@pytest.mark.usefixtures("db")
def test_show_group() -> None:
    result = run(["show", "internet"])
    assert result.output == dedent("""\
        github:
          password: gh
          username: takis
        reddit:
          password: rdt
          username: sakis
    """)


@pytest.mark.usefixtures("db")
def test_show_group_with_trailing_slash() -> None:
    result = run(["show", "internet/"])
    assert result.output == dedent("""\
        github:
          password: gh
          username: takis
        reddit:
          password: rdt
          username: sakis
    """)


@pytest.mark.usefixtures("db")
def test_show_color(editor: Callable) -> None:
    # Insert a new entry with a list
    editor(
        updated=dedent("""\
        username: user
        password: pass
        keywords:
        - youtube
        - gmail
    """),
    )
    run(["edit", "group/google"])

    # Test show without color
    expected = dedent("""\
        google:
          username: user
          password: pass
          keywords:
          - youtube
          - gmail
    """)
    result = run(["--no-color", "show", "group"])
    assert result.output == expected

    # Test show with color
    expected = dedent("""\
        \033[38;5;12mgoogle\033[38;5;11m:\033[0m
        \033[38;5;12m  username\033[38;5;11m:\033[0m user
        \033[38;5;12m  password\033[38;5;11m:\033[0m pass
        \033[38;5;12m  keywords\033[38;5;11m:\033[0m
        \033[38;5;9m  - \033[0myoutube
        \033[38;5;9m  - \033[0mgmail
    """)
    result = run(["--color", "show", "group"])
    assert result.output == expected
