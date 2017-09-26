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

"""Tests for passata generate."""

import click
import pytest

import passata
from tests.helpers import clipboard, read, run


def test_generate_password():
    alphanumeric = ('abcdefghijklmnopqrstuvwxyz'
                    'ABCDEFGHIJKLMNOPQRSTUVWXYZ'
                    '0123456789')
    symbols = '!"#$%&\'()*+,-./:;<=>?@[\]^_`{|}~'

    password = passata.generate_password(10, False)
    assert len(password) == 10
    assert all(char in alphanumeric for char in password)

    password = passata.generate_password(17, True)
    assert len(password) == 17
    assert all(char in alphanumeric + symbols for char in password)


def test_generate(monkeypatch, db):
    monkeypatch.setattr(passata, 'generate_password', lambda l, s: l * 'x')

    # Too short
    result = run(['generate', '--length=2'])
    assert result.exit_code == 2
    assert 'Error' in result.output

    # Generate and print
    result = run(['generate'])
    assert result.output == 'xxxxxxxxxxxxxxxxxxxx\n'

    # Generate and put to clipboard
    result = run(['generate', '--clipboard'])
    assert result.output == ("Put generated password to clipboard "
                             "(will disappear after pasted twice)\n")
    assert clipboard() == 'xxxxxxxxxxxxxxxxxxxx'
    assert clipboard() == 'xxxxxxxxxxxxxxxxxxxx'
    with pytest.raises(SystemExit):
        clipboard()

    # Generate, put in new entry and print
    result = run(['generate', 'asdf/test', '--length=5', '--force'])
    assert result.output == 'xxxxx\n'

    # Generate, put in existing entry and put to clipboard
    monkeypatch.setattr(click, 'pause',
                        lambda: print("Press any key to continue ..."))
    result = run(['generate', 'asdf/test', '--length=7', '--force',
                  '--clipboard'])
    assert result.output == ("Put old password to clipboard "
                             "(will disappear after pasted)\n"
                             "Press any key to continue ...\n"
                             "Put generated password to clipboard "
                             "(will disappear after pasted twice)\n")
    assert clipboard() == 'xxxxxxx'
    assert clipboard() == 'xxxxxxx'
    with pytest.raises(SystemExit):
        clipboard()

    assert read(db) == (
        'internet:\n'
        '  reddit:\n'
        '    password: rdt\n'
        '    username: sakis\n'
        '  github:\n'
        '    password: gh\n'
        '    username: takis\n'
        'asdf:\n'
        '  test:\n'
        '    password: xxxxxxx\n'
        '    old_password: xxxxx\n'
    )
