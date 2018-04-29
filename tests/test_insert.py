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

import click

from tests.helpers import read, run


def test_insert_to_group(db):
    result = run(['insert', 'group', '--password=pass'])
    assert isinstance(result.exception, SystemExit)
    assert result.output == 'group is a group\n'


def test_insert_entry(db):
    run(['insert', 'group/test', '--password=pass'])
    assert read(db) == (
        'internet:\n'
        '  reddit:\n'
        '    password: rdt\n'
        '    username: sakis\n'
        '  github:\n'
        '    password: gh\n'
        '    username: takis\n'
        'group:\n'
        '  test:\n'
        '    password: pass\n')


def test_insert_force_update(db):
    run(['insert', 'internet/reddit', '--force', '--password=newpass'])
    assert read(db) == (
        'internet:\n'
        '  reddit:\n'
        '    password: newpass\n'
        '    username: sakis\n'
        '    old_password: rdt\n'
        '  github:\n'
        '    password: gh\n'
        '    username: takis\n'
    )


def test_insert_confirm_update(monkeypatch, db):
    monkeypatch.setattr(click, 'confirm', lambda m: confirm)
    confirm = True
    run(['insert', 'internet/reddit', '--password=newpass'])
    assert read(db) == (
        'internet:\n'
        '  reddit:\n'
        '    password: newpass\n'
        '    username: sakis\n'
        '    old_password: rdt\n'
        '  github:\n'
        '    password: gh\n'
        '    username: takis\n'
    )


def test_insert_do_not_confirm_update(monkeypatch, db):
    monkeypatch.setattr(click, 'confirm', lambda m: confirm)
    confirm = False
    result = run(['insert', 'internet/reddit', '--password=newpass'])
    assert result.exception is None
    assert read(db) == (
        'internet:\n'
        '  reddit:\n'
        '    password: rdt\n'
        '    username: sakis\n'
        '  github:\n'
        '    password: gh\n'
        '    username: takis\n'
    )


def test_insert_no_password_no_backup(monkeypatch, db):
    monkeypatch.setattr(click, 'edit', lambda x, editor, extension: updated)
    updated = 'username: user\n'
    run(['edit', 'group/test'])
    run(['insert', 'group/test', '--password=pass'])
    assert read(db) == (
        'internet:\n'
        '  reddit:\n'
        '    password: rdt\n'
        '    username: sakis\n'
        '  github:\n'
        '    password: gh\n'
        '    username: takis\n'
        'group:\n'
        '  test:\n'
        '    username: user\n'
        '    password: pass\n'
    )
