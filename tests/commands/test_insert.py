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

"""Tests for passata insert."""

from collections.abc import Callable
from pathlib import Path
from textwrap import dedent

import click
import pytest

from tests.helpers import read, run


@pytest.mark.usefixtures("db")
def test_insert_top_level_entry(db: Path) -> None:
    run(["insert", "toplevel", "--password=pass"])

    assert read(db) == dedent("""\
        internet:
          github:
            password: gh
            username: takis
          reddit:
            password: rdt
            username: sakis
        toplevel:
          password: pass
    """)


@pytest.mark.usefixtures("db")
def test_insert_to_existing_group() -> None:
    result = run(["insert", "internet", "--password=pass"])

    assert isinstance(result.exception, SystemExit)
    assert result.output == "internet is a group\n"


def test_insert_entry(db: Path) -> None:
    run(["insert", "group/test", "--password=pass"])

    assert read(db) == dedent("""\
        internet:
          github:
            password: gh
            username: takis
          reddit:
            password: rdt
            username: sakis
        group:
          test:
            password: pass
    """)


def test_insert_force_update(db: Path) -> None:
    run(["insert", "internet/reddit", "--force", "--password=newpass"])

    assert read(db) == dedent("""\
        internet:
          github:
            password: gh
            username: takis
          reddit:
            password: newpass
            username: sakis
            old_password: rdt
    """)


def test_insert_confirm_update(monkeypatch: pytest.MonkeyPatch, db: Path) -> None:
    monkeypatch.setattr(click, "confirm", lambda _: True)

    run(["insert", "internet/reddit", "--password=newpass"])

    assert read(db) == dedent("""\
        internet:
          github:
            password: gh
            username: takis
          reddit:
            password: newpass
            username: sakis
            old_password: rdt
    """)


def test_insert_do_not_confirm_update(
    monkeypatch: pytest.MonkeyPatch,
    db: Path,
) -> None:
    monkeypatch.setattr(click, "confirm", lambda _: False)

    result = run(["insert", "internet/reddit", "--password=newpass"])

    assert result.exception is None
    assert read(db) == dedent("""\
        internet:
          github:
            password: gh
            username: takis
          reddit:
            password: rdt
            username: sakis
    """)


def test_insert_no_password_no_backup(db: Path, editor: Callable) -> None:
    editor(updated="username: user\n")
    run(["edit", "group/test"])

    run(["insert", "group/test", "--password=pass"])

    assert read(db) == dedent("""\
        internet:
          github:
            password: gh
            username: takis
          reddit:
            password: rdt
            username: sakis
        group:
          test:
            username: user
            password: pass
    """)


def test_insert_sort(db: Path) -> None:
    run(["insert", "internet/asdf", "--password=pass"])

    assert read(db) == dedent("""\
        internet:
          asdf:
            password: pass
          github:
            password: gh
            username: takis
          reddit:
            password: rdt
            username: sakis
    """)


# Tests for nested/filesystem-like paths


def test_insert_deeply_nested(db: Path) -> None:
    run(["insert", "a/b/c/d", "--password=deep"])

    assert read(db) == dedent("""\
        internet:
          github:
            password: gh
            username: takis
          reddit:
            password: rdt
            username: sakis
        a:
          b:
            c:
              d:
                password: deep
    """)


def test_insert_into_existing_nested_group(nested_db: Path) -> None:
    run(["insert", "internet/social/facebook", "--password=fb"])

    assert "facebook" in nested_db.read_text()


@pytest.mark.usefixtures("nested_db")
def test_insert_to_existing_nested_group_error() -> None:
    result = run(["insert", "internet/social", "--password=pass"])

    assert isinstance(result.exception, SystemExit)
    assert result.output == "internet/social is a group\n"
