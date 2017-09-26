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

import click

from tests.helpers import read, run


def test_edit_entry(monkeypatch, db):
    monkeypatch.setattr(click, 'edit', lambda x, editor, extension: updated)
    monkeypatch.setattr(click, 'confirm', lambda m: confirm)
    updated = (
        'username: sakis\n'
        'password: yolo\n'
    )
    confirm = True
    run(['edit', 'internet/reddit'])
    assert read(db) == (
        'internet:\n'
        '  reddit:\n'
        '    username: sakis\n'
        '    password: yolo\n'
        '  github:\n'
        '    password: gh\n'
        '    username: takis\n'
    )


def test_edit_new_entry_in_existing_group(monkeypatch, db):
    monkeypatch.setattr(click, 'edit', lambda x, editor, extension: updated)
    updated = (
        'username: takis\n'
        'password: secret\n'
    )
    run(['edit', 'internet/stack overflow'])
    assert read(db) == (
        'internet:\n'
        '  reddit:\n'
        '    password: rdt\n'
        '    username: sakis\n'
        '  github:\n'
        '    password: gh\n'
        '    username: takis\n'
        '  stack overflow:\n'
        '    username: takis\n'
        '    password: secret\n'
    )


def test_edit_new_entry_in_new_group(monkeypatch, db):
    monkeypatch.setattr(click, 'edit', lambda x, editor, extension: updated)
    updated = (
        'username: sakis\n'
        'password: yolo\n'
    )
    run(['edit', 'mail/gmail'])
    assert read(db) == (
        'internet:\n'
        '  reddit:\n'
        '    password: rdt\n'
        '    username: sakis\n'
        '  github:\n'
        '    password: gh\n'
        '    username: takis\n'
        'mail:\n'
        '  gmail:\n'
        '    username: sakis\n'
        '    password: yolo\n'
    )


def test_edit_delete_entry(monkeypatch, db):
    monkeypatch.setattr(click, 'edit', lambda x, editor, extension: updated)
    monkeypatch.setattr(click, 'confirm', lambda m: confirm)
    updated = ''
    # Do not confirm
    confirm = False
    run(['edit', 'internet/reddit'])
    assert read(db) == (
        'internet:\n'
        '  reddit:\n'
        '    password: rdt\n'
        '    username: sakis\n'
        '  github:\n'
        '    password: gh\n'
        '    username: takis\n'
    )
    # Confirm
    confirm = True
    run(['edit', 'internet/reddit'])
    assert read(db) == (
        'internet:\n'
        '  github:\n'
        '    password: gh\n'
        '    username: takis\n'
    )


def test_edit_delete_nonexistent_entry(monkeypatch, db):
    monkeypatch.setattr(click, 'edit', lambda x, editor, extension: updated)
    updated = ''
    run(['edit', 'asdf/asdf'])
    assert read(db) == (
        'internet:\n'
        '  reddit:\n'
        '    password: rdt\n'
        '    username: sakis\n'
        '  github:\n'
        '    password: gh\n'
        '    username: takis\n'
    )


def test_edit_group(monkeypatch, db):
    monkeypatch.setattr(click, 'edit', lambda x, editor, extension: updated)
    monkeypatch.setattr(click, 'confirm', lambda m: confirm)
    updated = (
        'reddit:\n'
        '  username: takis\n'
        '  password: secret\n'
    )
    confirm = True
    run(['edit', 'internet'])
    assert read(db) == (
        'internet:\n'
        '  reddit:\n'
        '    username: takis\n'
        '    password: secret\n'
    )


def test_edit_delete_group(monkeypatch, db):
    monkeypatch.setattr(click, 'edit', lambda x, editor, extension: updated)
    monkeypatch.setattr(click, 'confirm', lambda m: confirm)
    # Do not confirm
    updated = ''
    confirm = False
    run(['edit', 'internet'])
    assert read(db) == (
        'internet:\n'
        '  reddit:\n'
        '    password: rdt\n'
        '    username: sakis\n'
        '  github:\n'
        '    password: gh\n'
        '    username: takis\n'
    )
    # Confirm
    confirm = True
    run(['edit', 'internet'])
    assert read(db) == ''


def test_edit_delete_nonexistent_group(monkeypatch, db):
    monkeypatch.setattr(click, 'edit', lambda x, editor, extension: updated)
    updated = ''
    run(['edit', 'asdf'])
    assert read(db) == (
        'internet:\n'
        '  reddit:\n'
        '    password: rdt\n'
        '    username: sakis\n'
        '  github:\n'
        '    password: gh\n'
        '    username: takis\n'
    )


def test_edit_database(monkeypatch, db):
    monkeypatch.setattr(click, 'edit', lambda x, editor, extension: updated)
    monkeypatch.setattr(click, 'confirm', lambda m: confirm)
    updated = (
        'internet:\n'
        '  reddit:\n'
        '    password: rdt\n'
        '    username: sakis\n'
    )
    confirm = True
    run(['edit'])
    assert read(db) == updated


def test_edit_delete_database(monkeypatch, db):
    monkeypatch.setattr(click, 'edit', lambda x, editor, extension: updated)
    monkeypatch.setattr(click, 'confirm', lambda m: confirm)
    original = read(db)
    updated = ''
    # Do not confirm
    confirm = False
    run(['edit'])
    assert read(db) == original
    # Confirm
    confirm = True
    run(['edit'])
    assert read(db) == ''
