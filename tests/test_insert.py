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


def test_insert(monkeypatch, db):
    monkeypatch.setattr(click, 'confirm', lambda m: confirm)

    # Try to insert group
    result = run(['insert', 'group', '--password=...'])
    assert isinstance(result.exception, SystemExit)
    assert result.output == 'group is a group\n'

    # Insert entry
    run(['insert', 'group/test', '--password=one'])
    assert (
        'group:\n'
        '  test:\n'
        '    password: one\n'
    ) in read(db)

    # Force update
    run(['insert', 'group/test', '--force', '--password=two'])
    assert (
        'group:\n'
        '  test:\n'
        '    password: two\n'
        '    old_password: one\n'
    ) in read(db)

    # Confirm update
    confirm = True
    run(['insert', 'group/test', '--password=three'])
    assert (
        'group:\n'
        '  test:\n'
        '    password: three\n'
        '    old_password: two\n'
    ) in read(db)

    # Do not confirm update
    confirm = False
    result = run(['insert', 'group/test', '--password=four'])
    assert result.exception is None
    assert (
        'group:\n'
        '  test:\n'
        '    password: three\n'
        '    old_password: two\n'
    ) in read(db)

    # Add an entry with no password so there's no need for a backup
    monkeypatch.setattr(click, 'edit', lambda x, editor, extension: updated)
    updated = 'username: user\n'
    run(['edit', 'group/test'])
    run(['insert', 'group/test', '--force', '--password=five'])
    assert (
        'group:\n'
        '  test:\n'
        '    username: user\n'
        '    password: five\n'
    ) in read(db)
