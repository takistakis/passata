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

"""Tests for passata find."""

from collections.abc import Callable
from pathlib import Path
from textwrap import dedent

import pytest

from tests.helpers import clipboard, run


@pytest.mark.usefixtures("db")
def test_find() -> None:
    result = run(["find", "red"])

    assert result.output == dedent("""\
        internet
        └── reddit
    """)


@pytest.mark.usefixtures("db")
def test_find_multiple() -> None:
    result = run(["find", "red", "git"])

    assert result.output == dedent("""\
        internet
        ├── github
        └── reddit
    """)


@pytest.mark.usefixtures("db")
def test_find_multiple_clip() -> None:
    result = run(["find", "red", "git", "--clip"])

    assert result.output == dedent("""\
        internet
        ├── github
        └── reddit

        Copied password of internet/github to clipboard.
    """)
    assert clipboard() == "gh"


@pytest.mark.usefixtures("db")
def test_find_show() -> None:
    result = run(["find", "red", "--print"])

    assert result.output == dedent("""\
        internet:
          reddit:
            password: rdt
            username: sakis
    """)


@pytest.mark.usefixtures("db")
def test_find_no_results() -> None:
    result = run(["find", "asdf"])
    assert result.output == ""


@pytest.mark.usefixtures("db")
def test_find_in_keyword(editor: Callable) -> None:
    editor(
        updated=dedent("""
        username: user
        password: pass
        autotype: <username> Return !1.5 <password> Return
        keywords:
        - youtube
        - gmail
    """),
    )
    run(["edit", "group/google"])

    result = run(["find", "mail"])

    assert result.output == dedent("""\
        group
        └── google (gmail)
    """)


@pytest.mark.usefixtures("db")
def test_find_show_in_keyword(editor: Callable) -> None:
    editor(
        updated=dedent("""\
        username: user
        password: pass
        autotype: <username> Return !1.5 <password> Return
        keywords:
        - youtube
        - gmail
    """),
    )
    run(["edit", "group/google"])

    result = run(["find", "mail", "--print"])

    assert result.output == dedent("""\
        group:
          google (gmail):
            username: user
            password: pass
            autotype: <username> Return !1.5 <password> Return
            keywords:
            - youtube
            - gmail
    """)


def test_find_clip_no_password(db: Path) -> None:
    db.write_text(db.read_text() + "mail:\n  gmail:\n    username: user\n")
    result = run(["find", "gmail", "--clip"])
    assert isinstance(result.exception, SystemExit)
    assert result.output.endswith("does not have a password\n")


# Tests for nested/filesystem-like paths


@pytest.mark.usefixtures("nested_db")
def test_find_nested_entry() -> None:
    result = run(["find", "reddit"])

    assert "reddit" in result.output


@pytest.mark.usefixtures("nested_db")
def test_find_by_group_name() -> None:
    """Searching for a group name should find entries inside it."""
    result = run(["find", "social"])

    assert "reddit" in result.output
    assert "twitter" in result.output


@pytest.mark.usefixtures("nested_db")
def test_find_top_level_entry() -> None:
    result = run(["find", "server"])

    assert "server" in result.output
