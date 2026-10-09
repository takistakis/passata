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

"""Tests for passata rm."""

from copy import deepcopy
from pathlib import Path
from textwrap import dedent

import click
import pytest

import passata
from tests.helpers import read, run


def test_rm_group_without_recursive(db: Path) -> None:
    result = run(["rm", "--force", "internet"])

    assert isinstance(result.exception, SystemExit)
    assert result.output == "Cannot remove 'internet': is a group, use -r to remove\n"

    # Database should be unchanged
    assert read(db) == dedent("""\
        internet:
          github:
            password: gh
            username: takis
          reddit:
            password: rdt
            username: sakis
    """)


def test_rm_entry(monkeypatch: pytest.MonkeyPatch, db: Path) -> None:
    # Normal removal
    run(["rm", "--force", "internet/reddit"])

    assert read(db) == dedent("""\
        internet:
          github:
            password: gh
            username: takis
    """)

    # Remove nonexistent entry
    result = run(["rm", "internet/nonexistent"])

    assert isinstance(result.exception, SystemExit)
    assert result.output == "internet/nonexistent not found\n"

    # Do not confirm removal
    monkeypatch.setattr(click, "confirm", lambda _: False)

    run(["rm", "internet/github"])

    assert read(db) == dedent("""\
        internet:
          github:
            password: gh
            username: takis
    """)

    # Remove last entry
    run(["rm", "--force", "internet/github"])

    assert read(db) == ""


def test_rm_entries(db: Path) -> None:
    run(["rm", "--force", "internet/reddit", "internet/github"])

    assert read(db) == ""

    result = run(["rm", "--force", "asdf/asdf", "asdf/asdf2"])

    assert isinstance(result.exception, SystemExit)
    assert result.output == "asdf/asdf not found\n"


def test_rm_group(db: Path) -> None:
    result = run(["rm", "--force", "asdf"])

    assert isinstance(result.exception, SystemExit)
    assert result.output == "asdf not found\n"

    run(["rm", "--force", "--recursive", "internet"])

    assert read(db) == ""


# Tests for nested/filesystem-like paths


def test_rm_nested_entry(nested_db: Path) -> None:
    run(["rm", "--force", "internet/social/reddit"])

    content = nested_db.read_text()
    assert "reddit" not in content
    assert "twitter" in content


def test_rm_nested_group(nested_db: Path) -> None:
    run(["rm", "--force", "--recursive", "internet/social"])

    content = nested_db.read_text()
    assert "social" not in content
    assert "github" in content


def test_rm_top_level_entry(nested_db: Path) -> None:
    run(["rm", "--force", "server"])

    content = nested_db.read_text()
    assert "server" not in content
    assert "internet" in content


def test_rm_nested_cleans_empty_parents(nested_db: Path) -> None:
    run(["rm", "--force", "internet/social/reddit"])
    run(["rm", "--force", "internet/social/twitter"])

    content = nested_db.read_text()
    # social group should be gone since both children were removed
    assert "social" not in content
    assert "github" in content


@pytest.mark.parametrize("contents", [None, ""])
def test_rm_whole_database(db: Path, contents: str | None) -> None:
    if contents is not None:
        db.write_text(contents)
    result = run(["rm", "--force", "--recursive", "/"])

    assert result.exit_code == 0
    assert result.exception is None
    assert read(db) == ""


def test_rm_whole_database_declined(db: Path) -> None:
    original = read(db)
    result = run(["rm", "--recursive", "/"], input_="n\n")

    assert result.exit_code == 0
    assert "Delete the whole database?" in result.output
    assert read(db) == original


def test_rm_late_failure_is_atomic(db: Path) -> None:
    original = read(db)
    result = run(["rm", "--force", "internet/reddit", "missing"])

    assert result.exit_code == 1
    assert result.output == "missing not found\n"
    assert read(db) == original


def test_rm_late_failure_preserves_memory(
    db: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    database = passata.DB(db)
    database.read()
    original = deepcopy(database.db)
    monkeypatch.setattr(database, "read", lambda **_: None)
    with (
        click.Context(passata.cli, obj={"_db": database, "gpg_id": "unused"}) as ctx,
        pytest.raises(SystemExit, match="missing not found"),
    ):
        ctx.invoke(
            passata.rm,
            names=["internet/reddit", "missing"],
            force=True,
            recursive=False,
        )
    assert database.db == original
