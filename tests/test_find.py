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

"""Tests for passata find."""

import click

from tests.helpers import run


def test_find(db):
    result = run(['find', 'red'])
    assert result.output == (
        'internet\n'
        '└── reddit\n'
    )


def test_find_multiple(db):
    result = run(['find', 'red', 'git'])
    assert result.output == (
        'internet\n'
        '├── reddit\n'
        '└── github\n'
    )


def test_find_show(db):
    result = run(['find', 'red', '--show'])
    assert result.output == (
        'internet:\n'
        '  reddit:\n'
        '    password: rdt\n'
        '    username: sakis\n'
    )


def test_find_no_results(db):
    result = run(['find', 'asdf'])
    assert result.output == ''


def test_find_in_keyword(monkeypatch, db):
    monkeypatch.setattr(click, 'edit', lambda x, editor, extension: updated)
    updated = (
        'username: user\n'
        'password: pass\n'
        'autotype: <username> Return !1.5 <password> Return\n'
        'keywords:\n'
        '- youtube\n'
        '- gmail\n'
    )
    run(['edit', 'group/google'])

    result = run(['find', 'mail'])
    assert result.output == (
        'group\n'
        '└── google (gmail)\n'
    )


def test_find_show_in_keyword(monkeypatch, db):
    monkeypatch.setattr(click, 'edit', lambda x, editor, extension: updated)
    updated = (
        'username: user\n'
        'password: pass\n'
        'autotype: <username> Return !1.5 <password> Return\n'
        'keywords:\n'
        '- youtube\n'
        '- gmail\n'
    )
    run(['edit', 'group/google'])

    result = run(['find', 'mail', '--show'])
    assert result.output == (
        'group:\n'
        '  google (gmail):\n'
        '    username: user\n'
        '    password: pass\n'
        '    autotype: <username> Return !1.5 <password> Return\n'
        '    keywords:\n'
        '    - youtube\n'
        '    - gmail\n'
    )
