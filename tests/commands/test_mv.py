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

"""Tests for passata mv."""

from copy import deepcopy
from textwrap import dedent

import click
import pytest

import passata
from passata import Path
from tests.helpers import read, run


def test_mv_entry_to_entry(db: Path) -> None:
    result = run(["mv", "internet/reddit", "internet/rdt"])

    assert result.exit_code == 0
    assert result.exception is None
    assert read(db) == dedent("""\
        internet:
          github:
            password: gh
            username: takis
          rdt:
            password: rdt
            username: sakis
    """)


def test_mv_entry_to_new_name(db: Path) -> None:
    run(["mv", "internet/reddit", "new"])

    assert read(db) == dedent("""\
        internet:
          github:
            password: gh
            username: takis
        new:
          password: rdt
          username: sakis
    """)


def test_mv_entry_to_group(db: Path) -> None:
    run(["mv", "internet/reddit", "new/"])

    assert read(db) == dedent("""\
        internet:
          github:
            password: gh
            username: takis
        new:
          reddit:
            password: rdt
            username: sakis
    """)


@pytest.mark.usefixtures("db")
def test_mv_entries_to_entry() -> None:
    result = run(["mv", "internet/reddit", "internet/github", "new/new"])

    assert isinstance(result.exception, SystemExit)
    assert result.output == "new/new is not a group\n"


def test_mv_entries_to_group(db: Path) -> None:
    run(["mv", "internet/reddit", "internet/github", "new/"])

    assert read(db) == dedent("""\
        new:
          github:
            password: gh
            username: takis
          reddit:
            password: rdt
            username: sakis
    """)


@pytest.mark.usefixtures("db")
def test_mv_multiple_sources_with_missing_source() -> None:
    result = run(
        ["mv", "internet/reddit", "internet/nonexistent", "/"],
    )

    assert isinstance(result.exception, SystemExit)
    assert result.output == "internet/nonexistent not found\n"


def test_mv_group_to_group(db: Path) -> None:
    run(["mv", "internet", "test"])

    assert read(db) == dedent("""\
        test:
          github:
            password: gh
            username: takis
          reddit:
            password: rdt
            username: sakis
    """)


@pytest.mark.usefixtures("db")
def test_mv_group_to_entry() -> None:
    result = run(["mv", "internet", "internet/github"])

    assert isinstance(result.exception, SystemExit)
    assert result.output == "internet/github already exists\n"


@pytest.mark.usefixtures("db")
def test_mv_nonexistent_entry() -> None:
    result = run(["mv", "internet/nonexistent", "group"])

    assert isinstance(result.exception, SystemExit)
    assert result.output == "internet/nonexistent not found\n"


@pytest.mark.usefixtures("db")
def test_mv_nonexistent_group() -> None:
    result = run(["mv", "nonexistent", "group"])

    assert isinstance(result.exception, SystemExit)
    assert result.output == "nonexistent not found\n"


@pytest.mark.usefixtures("db")
def test_mv_group_to_existing_group() -> None:
    run(["insert", "group/test", "--password=pass"])

    result = run(["mv", "group", "internet"])

    assert isinstance(result.exception, SystemExit)
    assert result.output == "internet already exists\n"


def test_mv_overwrite(monkeypatch: pytest.MonkeyPatch, db: Path) -> None:
    monkeypatch.setattr(click, "confirm", lambda _: False)

    run(["mv", "internet/reddit", "internet/github"])

    assert read(db) == dedent("""\
        internet:
          github:
            password: gh
            username: takis
          reddit:
            password: rdt
            username: sakis
    """)

    monkeypatch.setattr(click, "confirm", lambda _: True)

    run(["mv", "internet/reddit", "internet/github"])

    assert read(db) == dedent("""\
        internet:
          github:
            password: rdt
            username: sakis
    """)


# Tests for nested/filesystem-like paths


def test_mv_nested_entry(nested_db: Path) -> None:
    run(["mv", "internet/social/reddit", "internet/reddit"])

    content = nested_db.read_text()
    assert "internet:\n" in content
    # reddit should be directly under internet now
    assert "  reddit:" in content


def test_mv_entry_to_nested_group(nested_db: Path) -> None:
    run(["mv", "internet/github", "internet/social/"])

    content = nested_db.read_text()
    # github should now be under social
    assert "social:" in content
    assert "github:" in content


@pytest.mark.usefixtures("nested_db")
def test_mv_into_own_subdirectory() -> None:
    result = run(["mv", "internet", "internet/social/deep"])

    assert isinstance(result.exception, SystemExit)
    assert "Cannot move" in result.output


def test_mv_entry_to_root(nested_db: Path) -> None:
    run(["mv", "internet/github", "/"])

    content = nested_db.read_text()
    # github should be at the top level now, not under internet
    assert "\ngithub:\n" in content or content.startswith("github:\n")
    assert "internet:" in content


def test_mv_entries_to_root(nested_db: Path) -> None:
    run(["mv", "internet/social/reddit", "internet/social/twitter", "/"])

    content = nested_db.read_text()
    # Both should be at top level now
    assert "reddit:" in content
    assert "twitter:" in content
    # social group should be gone (both children removed)
    assert "social" not in content


@pytest.mark.parametrize("source", ["/", "", "internet/github/password"])
def test_mv_rejects_non_node_sources(db: Path, source: str) -> None:
    original = read(db)
    result = run(["mv", "--force", source, "new"])

    assert result.exit_code == 1
    assert (
        "Cannot move the whole database" in result.output
        or "is not an entry or group" in result.output
    )
    assert read(db) == original


@pytest.mark.parametrize("dest", ["/invalid/", "invalid//group/"])
def test_mv_validates_group_destination_before_changes(db: Path, dest: str) -> None:
    original = read(db)
    result = run(["mv", "--force", "internet/reddit", dest])

    assert result.exit_code == 1
    assert result.output == f"Invalid path: {dest}\n"
    assert read(db) == original


def test_mv_multiple_groups_rejects_own_subdirectory(nested_db: Path) -> None:
    original = read(nested_db)
    result = run(["mv", "--force", "server", "internet", "internet/new/"])

    assert result.exit_code == 1
    assert "Cannot move 'internet' into its own subdirectory" in result.output
    assert read(nested_db) == original


def test_mv_trailing_slashes_on_multiple_sources(nested_db: Path) -> None:
    result = run(
        ["mv", "--force", "internet/social/", "internet/github/", "new/"],
    )

    assert result.exit_code == 0
    assert result.exception is None
    content = nested_db.read_text()
    assert "internet:" not in content
    assert "  social:" in content
    assert "  github:" in content


@pytest.mark.parametrize("cancelled", [False, True])
def test_mv_late_failure_or_cancellation_preserves_memory(
    db: Path,
    monkeypatch: pytest.MonkeyPatch,
    cancelled: bool,
) -> None:
    database = passata.DB(db)
    database.read()
    original = deepcopy(database.db)
    monkeypatch.setattr(database, "read", lambda **_: None)
    sources = (
        ("internet/reddit", "internet/github")
        if cancelled
        else ("internet/reddit", "missing")
    )
    monkeypatch.setattr(click, "confirm", lambda _: False)
    with (
        click.Context(passata.cli, obj={"_db": database, "gpg_id": "unused"}) as ctx,
        pytest.raises(SystemExit) as error,
    ):
        ctx.invoke(
            passata.mv,
            source=sources,
            dest="internet",
            force=not cancelled,
        )
    assert error.value.code == (0 if cancelled else "missing not found")
    assert database.db == original


@pytest.mark.parametrize("multiple", [False, True])
def test_mv_preserves_empty_groups(db: Path, multiple: bool) -> None:
    with db.open("a") as file:
        file.write("empty: {}\n")
    args = (
        ["mv", "--force", "empty", "internet/github", "new/"]
        if multiple
        else ["mv", "--force", "empty", "renamed"]
    )
    result = run(args)

    assert result.exit_code == 0
    assert result.exception is None
    database = passata.DB(db)
    database.read()
    assert database.get("new/empty" if multiple else "renamed") == {}
    assert database.get("empty") is None


def test_mv_empty_group_overwrites_destination(db: Path) -> None:
    with db.open("a") as file:
        file.write("empty: {}\nnew:\n  empty:\n    password: original\n")
    result = run(["mv", "--force", "empty", "internet/github", "new/"])

    assert result.exit_code == 0
    database = passata.DB(db)
    database.read()
    assert database.get("new/empty") == {}
    assert database.get("new/github") is not None
    assert database.get("empty") is None
