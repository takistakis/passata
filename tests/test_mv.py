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

from textwrap import dedent

import click

from tests.helpers import read, run


def test_mv_entry_to_entry(db):
    result = run(["mv", "internet/reddit", "internet/rdt"])
    assert result.exit_code == 0
    assert result.exception is None
    assert read(db) == dedent(
        """\
        internet:
          github:
            password: gh
            username: takis
          rdt:
            password: rdt
            username: sakis
        """
    )


def test_mv_entry_to_group(db):
    run(["mv", "internet/reddit", "new"])
    assert read(db) == dedent(
        """\
        internet:
          github:
            password: gh
            username: takis
        new:
          reddit:
            password: rdt
            username: sakis
        """
    )


def test_mv_entries_to_entry(db):
    result = run(["mv", "internet/reddit", "internet/github", "new/new"])
    assert isinstance(result.exception, SystemExit)
    assert result.output == "new/new is not a group\n"


def test_mv_entries_to_group(db):
    run(["mv", "internet/reddit", "internet/github", "new"])
    assert read(db) == dedent(
        """\
        new:
          github:
            password: gh
            username: takis
          reddit:
            password: rdt
            username: sakis
        """
    )


def test_mv_group_to_group(db):
    run(["mv", "internet", "test"])
    assert read(db) == dedent(
        """\
        test:
          github:
            password: gh
            username: takis
          reddit:
            password: rdt
            username: sakis
        """
    )


def test_mv_group_to_entry(db):
    result = run(["mv", "internet", "internet/github"])
    assert isinstance(result.exception, SystemExit)
    assert result.output == "internet/github is not a group\n"


def test_mv_nonexistent_entry(db):
    result = run(["mv", "internet/nonexistent", "group"])
    assert isinstance(result.exception, SystemExit)
    assert result.output == "internet/nonexistent not found\n"


def test_mv_nonexistent_group(db):
    result = run(["mv", "nonexistent", "group"])
    assert isinstance(result.exception, SystemExit)
    assert result.output == "nonexistent not found\n"


def test_mv_group_to_existing_group(db):
    run(["insert", "group/test", "--password=pass"])
    result = run(["mv", "group", "internet"])
    assert isinstance(result.exception, SystemExit)
    assert result.output == "internet already exists\n"


def test_mv_overwrite(monkeypatch, db):
    monkeypatch.setattr(click, "confirm", lambda m: confirm)

    confirm = False
    run(["mv", "internet/reddit", "internet/github"])

    assert read(db) == dedent(
        """\
        internet:
          github:
            password: gh
            username: takis
          reddit:
            password: rdt
            username: sakis
        """
    )

    confirm = True
    run(["mv", "internet/reddit", "internet/github"])

    assert read(db) == dedent(
        """\
        internet:
          github:
            password: rdt
            username: sakis
        """
    )
