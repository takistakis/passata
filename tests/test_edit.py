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

"""Tests for passata edit."""

from collections.abc import Callable
from pathlib import Path
from textwrap import dedent

import click
import pytest

import passata
from tests.helpers import read, run


def test_edit_entry(
    monkeypatch: pytest.MonkeyPatch,
    db: Path,
    editor: Callable,
) -> None:
    monkeypatch.setattr(click, "confirm", lambda _: True)
    editor(
        updated=dedent("""
        username: sakis
        password: yolo
    """),
    )
    run(["edit", "internet/reddit"])
    assert read(db) == dedent("""\
        internet:
          github:
            password: gh
            username: takis
          reddit:
            username: sakis
            password: yolo
    """)


def test_edit_new_entry_in_existing_group(db: Path, editor: Callable) -> None:
    editor(
        updated=dedent("""\
        username: takis
        password: secret
    """),
    )
    result = run(["edit", "internet/stack overflow"])
    assert result.exit_code == 0
    assert result.exception is None
    assert read(db) == dedent("""\
        internet:
          github:
            password: gh
            username: takis
          reddit:
            password: rdt
            username: sakis
          stack overflow:
            username: takis
            password: secret
    """)


def test_edit_new_entry_in_new_group(db: Path, editor: Callable) -> None:
    editor(
        updated=dedent("""\
        username: sakis
        password: yolo
    """),
    )
    run(["edit", "mail/gmail"])
    assert read(db) == dedent("""\
        internet:
          github:
            password: gh
            username: takis
          reddit:
            password: rdt
            username: sakis
        mail:
          gmail:
            username: sakis
            password: yolo
    """)


def test_edit_delete_entry(
    monkeypatch: pytest.MonkeyPatch,
    db: Path,
    editor: Callable,
) -> None:
    editor(updated="")
    # Do not confirm
    monkeypatch.setattr(click, "confirm", lambda _: False)
    result = run(["edit", "internet/reddit"])
    assert result.exit_code == 0
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
    passata.unlock_file(db)
    # Confirm
    monkeypatch.setattr(click, "confirm", lambda _: True)
    result = run(["edit", "internet/reddit"])
    assert result.exit_code == 0
    assert result.exception is None
    assert read(db) == dedent("""\
        internet:
          github:
            password: gh
            username: takis
    """)


def test_edit_delete_nonexistent_entry(db: Path, editor: Callable) -> None:
    editor(updated="")
    run(["edit", "asdf/asdf"])
    assert read(db) == dedent("""\
        internet:
          github:
            password: gh
            username: takis
          reddit:
            password: rdt
            username: sakis
    """)


def test_edit_group(
    monkeypatch: pytest.MonkeyPatch,
    db: Path,
    editor: Callable,
) -> None:
    monkeypatch.setattr(click, "confirm", lambda _: True)
    editor(
        updated=dedent("""\
        reddit:
          username: takis
          password: secret
    """),
    )
    run(["edit", "internet"])
    assert read(db) == dedent("""\
        internet:
          reddit:
            username: takis
            password: secret
    """)


def test_edit_delete_group(
    monkeypatch: pytest.MonkeyPatch,
    db: Path,
    editor: Callable,
) -> None:
    editor(updated="")
    # Do not confirm
    monkeypatch.setattr(click, "confirm", lambda _: False)
    run(["edit", "internet"])
    assert read(db) == dedent("""\
        internet:
          github:
            password: gh
            username: takis
          reddit:
            password: rdt
            username: sakis
    """)
    # Confirm
    monkeypatch.setattr(click, "confirm", lambda _: True)
    run(["edit", "internet"])
    assert read(db) == ""


def test_edit_delete_nonexistent_group(db: Path, editor: Callable) -> None:
    editor(updated="")
    run(["edit", "asdf"])
    assert read(db) == dedent("""\
        internet:
          github:
            password: gh
            username: takis
          reddit:
            password: rdt
            username: sakis
    """)


def test_edit_database(
    monkeypatch: pytest.MonkeyPatch,
    db: Path,
    editor: Callable,
) -> None:
    updated = dedent("""\
        internet:
          reddit:
            password: rdt
            username: sakis
    """)
    editor(updated=updated)
    monkeypatch.setattr(click, "confirm", lambda _: True)
    run(["edit"])
    assert read(db) == updated


def test_edit_delete_database(
    monkeypatch: pytest.MonkeyPatch,
    db: Path,
    editor: Callable,
) -> None:
    original = read(db)
    editor(updated="")
    # Do not confirm
    monkeypatch.setattr(click, "confirm", lambda _: False)
    result = run(["edit"])
    assert result.exit_code == 0
    assert result.exception is None
    assert read(db) == original
    passata.unlock_file(db)
    # Confirm
    monkeypatch.setattr(click, "confirm", lambda _: True)
    result = run(["edit"])
    assert result.exit_code == 0
    assert result.exception is None
    assert read(db) == ""


@pytest.mark.usefixtures("db")
def test_edit_invalid_yaml(
    monkeypatch: pytest.MonkeyPatch,
    editor: Callable,
) -> None:
    monkeypatch.setattr(click, "confirm", lambda _: True)
    editor(
        updated=dedent("""\
        username: sakis
        password
    """),
    )
    result = run(["edit", "internet/reddit"])
    assert result.exit_code == 1
    assert isinstance(result.exception, SystemExit)
    assert result.output == "Invalid yaml\n"
