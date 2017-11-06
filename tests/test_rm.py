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

import click

from tests.helpers import read, run


def test_rm_entry(monkeypatch, db):
    # Normal removal
    run(['rm', '--force', 'internet/reddit'])
    assert read(db) == (
        'internet:\n'
        '  github:\n'
        '    password: gh\n'
        '    username: takis\n'
    )

    # Remove nonexistent entry
    result = run(['rm', 'internet/nonexistent'])
    assert isinstance(result.exception, SystemExit)
    assert result.output == "internet/nonexistent not found\n"

    # Do not confirm removal
    monkeypatch.setattr(click, 'confirm', lambda m: False)
    run(['rm', 'internet/github'])
    assert read(db) == (
        'internet:\n'
        '  github:\n'
        '    password: gh\n'
        '    username: takis\n'
    )

    # Remove last entry
    run(['rm', '--force', 'internet/github'])
    assert read(db) == ''


def test_rm_entries(db):
    run(['rm', '--force', 'internet/reddit', 'internet/github'])
    assert read(db) == ''

    result = run(['rm', '--force', 'asdf/asdf', 'asdf/asdf2'])
    assert isinstance(result.exception, SystemExit)
    assert result.output == "asdf/asdf not found\n"


def test_rm_group(db):
    result = run(['rm', '--force', 'asdf'])
    assert isinstance(result.exception, SystemExit)
    assert result.output == "asdf not found\n"

    run(['rm', '--force', 'internet'])
    assert read(db) == ''
