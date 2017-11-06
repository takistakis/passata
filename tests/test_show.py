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

"""Tests for passata show."""

import functools

import click
import pytest

from tests.helpers import clipboard, run


def test_show(db):
    # Normal show
    result = run(['show', 'internet/github'])
    assert result.output == (
        'password: gh\n'
        'username: takis\n'
    )

    # Try to show a nonexistent entry
    result = run(['show', 'internet/nonexistent'])
    assert isinstance(result.exception, SystemExit)
    assert result.output == "internet/nonexistent not found\n"

    # Try to show an entry three levels deep
    result = run(['show', 'one/two/three'])
    assert isinstance(result.exception, SystemExit)
    assert result.output == "one/two/three is nested too deeply\n"

    # Clipboard
    result = run(['show', 'internet/github', '--clipboard'])
    assert result.output == ''
    assert clipboard() == 'gh'
    # Should be gone after being pasted
    with pytest.raises(SystemExit):
        clipboard()

    # Try to put the whole database to clipboard
    result = run(['show', '--clipboard'])
    assert isinstance(result.exception, SystemExit)
    assert result.output == "Can't put the entire database to clipboard\n"

    # Try to put a whole group to clipboard
    result = run(['show', 'internet', '--clipboard'])
    assert isinstance(result.exception, SystemExit)
    assert result.output == "Can't put the entire group to clipboard\n"

    # Show group
    expected = (
        'reddit:\n'
        '  password: rdt\n'
        '  username: sakis\n'
        'github:\n'
        '  password: gh\n'
        '  username: takis\n'
    )
    result = run(['show', 'internet'])
    assert result.output == expected

    # Show group with trailing slash
    result = run(['show', 'internet/'])
    assert result.output == expected


def test_show_color(monkeypatch, db):
    # Do not strip ANSI codes automatically
    color_echo = functools.partial(click.echo, color=True)
    monkeypatch.setattr(click, 'echo', color_echo)

    # Insert a new entry with a list
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

    # Test show without color
    expected = (
        'google:\n'
        '  username: user\n'
        '  password: pass\n'
        '  autotype: <username> Return !1.5 <password> Return\n'
        '  keywords:\n'
        '  - youtube\n'
        '  - gmail\n'
    )
    result = run(['show', 'group', '--no-color'])
    assert result.output == expected

    # Test show with color
    expected = (
        '\033[38;5;12mgoogle\033[38;5;11m:\033[0m\n'
        '\033[38;5;12m  username\033[38;5;11m:\033[0m user\n'
        '\033[38;5;12m  password\033[38;5;11m:\033[0m pass\n'
        '\033[38;5;12m  autotype\033[38;5;11m:\033[0m '
        '<username> Return !1.5 <password> Return\n'
        '\033[38;5;12m  keywords\033[38;5;11m:\033[0m\n'
        '\033[38;5;9m  - \033[0myoutube\n'
        '\033[38;5;9m  - \033[0mgmail\n'
    )
    result = run(['show', 'group', '--color'])
    assert result.output == expected
