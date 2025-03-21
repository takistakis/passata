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

from pathlib import Path
from textwrap import dedent
from typing import Callable

from tests.helpers import clipboard, run


def test_find(db: Path) -> None:
    result = run(["find", "red"])
    assert result.output == dedent(
        """\
        internet
        └── reddit
        """
    )


def test_find_multiple(db: Path) -> None:
    result = run(["find", "red", "git"])
    assert result.output == dedent(
        """\
        internet
        ├── github
        └── reddit
        """
    )


def test_find_multiple_clip(db: Path) -> None:
    result = run(["find", "red", "git", "--clip"])
    assert result.output == dedent(
        """\
        internet
        ├── github
        └── reddit

        Copied password of internet/github to clipboard.
        """
    )
    assert clipboard() == "gh"


def test_find_show(db: Path) -> None:
    result = run(["find", "red", "--print"])
    assert result.output == dedent(
        """\
        internet:
          reddit:
            password: rdt
            username: sakis
        """
    )


def test_find_no_results(db: Path) -> None:
    result = run(["find", "asdf"])
    assert result.output == ""


def test_find_in_keyword(db: Path, editor: Callable) -> None:
    editor(
        updated=dedent(
            """
            username: user
            password: pass
            autotype: <username> Return !1.5 <password> Return
            keywords:
            - youtube
            - gmail
            """
        )
    )
    run(["edit", "group/google"])

    result = run(["find", "mail"])
    assert result.output == dedent(
        """\
        group
        └── google (gmail)
        """
    )


def test_find_show_in_keyword(db: Path, editor: Callable) -> None:
    editor(
        updated=dedent(
            """\
            username: user
            password: pass
            autotype: <username> Return !1.5 <password> Return
            keywords:
            - youtube
            - gmail
            """
        )
    )
    run(["edit", "group/google"])

    result = run(["find", "mail", "--print"])
    assert result.output == dedent(
        """\
        group:
          google (gmail):
            username: user
            password: pass
            autotype: <username> Return !1.5 <password> Return
            keywords:
            - youtube
            - gmail
        """
    )
