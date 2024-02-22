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

from textwrap import dedent

import click

from tests.helpers import read, run


def test_insert_to_group(db):
    result = run(["insert", "group", "--password=pass"])
    assert isinstance(result.exception, SystemExit)
    assert result.output == "group is a group\n"


def test_insert_entry(db):
    run(["insert", "group/test", "--password=pass"])
    assert read(db) == dedent(
        """\
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
        """
    )


def test_insert_force_update(db):
    run(["insert", "internet/reddit", "--force", "--password=newpass"])
    assert read(db) == dedent(
        """\
        internet:
          github:
            password: gh
            username: takis
          reddit:
            password: newpass
            username: sakis
            old_password: rdt
        """
    )


def test_insert_confirm_update(monkeypatch, db):
    monkeypatch.setattr(click, "confirm", lambda m: confirm)
    confirm = True
    run(["insert", "internet/reddit", "--password=newpass"])
    assert read(db) == dedent(
        """\
        internet:
          github:
            password: gh
            username: takis
          reddit:
            password: newpass
            username: sakis
            old_password: rdt
        """
    )


def test_insert_do_not_confirm_update(monkeypatch, db):
    monkeypatch.setattr(click, "confirm", lambda m: confirm)
    confirm = False
    result = run(["insert", "internet/reddit", "--password=newpass"])
    assert result.exception is None
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


def test_insert_no_password_no_backup(db, editor):
    editor(updated="username: user\n")
    run(["edit", "group/test"])
    run(["insert", "group/test", "--password=pass"])
    assert read(db) == dedent(
        """\
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
        """
    )


def test_insert_sort(db):
    run(["insert", "internet/asdf", "--password=pass"])
    assert read(db) == dedent(
        """\
        internet:
          asdf:
            password: pass
          github:
            password: gh
            username: takis
          reddit:
            password: rdt
            username: sakis
        """
    )
