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

"""Tests for passata autotype."""

import pytest

import passata
from tests.helpers import run


def test_get_autotype(monkeypatch):
    # <autotype> field in entry
    entry = {'username': 'takis', 'password': 'pass',
             'autotype': '<password> !5 Return'}
    autotype = passata.get_autotype(entry)
    assert autotype == ['<password>', '!5', 'Return']

    # <username> and <password> fields in entry
    entry = {'username': 'takis', 'password': 'pass'}
    autotype = passata.get_autotype(entry)
    assert autotype == ['<username>', 'Tab', '<password>', 'Return']

    # <password> field in entry
    entry = {'name': 'takis', 'password': 'pass'}
    autotype = passata.get_autotype(entry)
    assert autotype == ['<password>', 'Return']

    # No known fields in entry
    # Suppress notification
    monkeypatch.setattr(passata, 'call', lambda command: None)
    entry = {'name': 'takis', 'pass': 'pass'}
    with pytest.raises(SystemExit):
        passata.get_autotype(entry)


def test_autotype(monkeypatch, db):
    monkeypatch.setattr(passata, 'active_window', lambda: (0, window_title))
    monkeypatch.setattr(passata, 'call', lambda command: print(command))

    window_title = 'GitHub: The world\'s leading blah blah blah'
    result = run(['autotype'])
    assert result.exception is None
    assert result.output == (
        "['xdotool', 'type', '--clearmodifiers', '--delay', '50', 'takis']\n"
        "['xdotool', 'key', 'Tab']\n"
        "['xdotool', 'type', '--clearmodifiers', '--delay', '50', 'gh']\n"
        "['xdotool', 'key', 'Return']\n"
    )


def test_autotype_no_username(monkeypatch, db):
    monkeypatch.setattr(passata, 'active_window', lambda: (0, window_title))
    monkeypatch.setattr(passata, 'call', lambda command: print(command))

    run(['insert', 'autotype/test1', '--password=pass1'])

    window_title = 'test1'
    result = run(['autotype'])
    assert result.exception is None
    assert result.output == (
        "['xdotool', 'type', '--clearmodifiers', '--delay', '50', 'pass1']\n"
        "['xdotool', 'key', 'Return']\n"
    )


def test_autotype_keywords_simple(monkeypatch, db, editor):
    monkeypatch.setattr(passata, 'active_window', lambda: (0, window_title))
    monkeypatch.setattr(passata, 'call', lambda command: print(command))

    # Add a new entry with a single string in keywords
    editor(updated=(
        'password: pass2\n'
        'keywords: the keyword\n'
    ))
    run(['edit', 'autotype/test2'])

    window_title = 'A website with the keyword in its title'
    result = run(['autotype'])
    assert result.exception is None
    assert result.output == (
        "['xdotool', 'type', '--clearmodifiers', '--delay', '50', 'pass2']\n"
        "['xdotool', 'key', 'Return']\n"
    )


def test_autotype_keywords_complex(monkeypatch, db, editor):
    monkeypatch.setattr(passata, 'active_window', lambda: (0, window_title))
    monkeypatch.setattr(passata, 'call', lambda command: print(command))

    # Add a new entry with an autotype field and a list of
    # strings in keywords that conflict with another entry.
    editor(updated=(
        'username: user3\n'
        'password: pass3\n'
        'keywords:\n'
        '- github\n'
        '- yoyoyo\n'
        'autotype: <username> Return !1.5 <password> Return\n'
    ))
    run(['edit', 'autotype/test3'])

    def fake_out(command, input):
        print('Calling', command)
        print('With input:')
        print(input)
        print()
        return 'autotype/test3'

    # Patch user interaction with dmenu to choose the new entry
    # and sleeping to just print for how long it would sleep.
    monkeypatch.setattr(passata, 'out', fake_out)
    monkeypatch.setattr('time.sleep',
                        lambda duration: print("Sleeping for", duration))

    window_title = 'GitHub'
    result = run(['autotype'])
    assert result.exception is None
    assert result.output == (
        "Calling ['dmenu']\n"
        "With input:\n"
        "autotype/test3\n"
        "internet/github\n"
        "\n"
        "['xdotool', 'type', '--clearmodifiers', '--delay', '50', 'user3']\n"
        "['xdotool', 'key', 'Return']\n"
        "Sleeping for 1.5\n"
        "['xdotool', 'type', '--clearmodifiers', '--delay', '50', 'pass3']\n"
        "['xdotool', 'key', 'Return']\n"
    )


def test_autotype_invalid(monkeypatch, db, editor):
    monkeypatch.setattr(passata, 'active_window', lambda: (0, window_title))
    # Suppress notification
    monkeypatch.setattr(passata, 'call', lambda command: None)

    editor(updated=(
        'password: pass4\n'
        'autotype: <username> Tab <password> Return\n'
    ))
    run(['edit', 'autotype/test4'])

    window_title = 'test4'
    result = run(['autotype'])
    assert isinstance(result.exception, SystemExit)
