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

ALPHANUMERIC = ('abcdefghijklmnopqrstuvwxyz'
                'ABCDEFGHIJKLMNOPQRSTUVWXYZ'
                '0123456789')

SYMBOLS = '!"#$%&\'()*+,-./:;<=>?@[\]^_`{|}~'


def test_generate_password_length_no_symbols():
    password = passata.generate_password(
        length=10, entropy=None, symbols=False, wordlist=None, force=False)
    assert len(password) == 10
    assert all(char in ALPHANUMERIC for char in password)
    assert not any(char in password for char in SYMBOLS)


def test_generate_password_length_symbols():
    password = passata.generate_password(
        length=17, entropy=None, symbols=True, wordlist=None, force=False)
    assert len(password) == 17
    assert all(char in ALPHANUMERIC + SYMBOLS for char in password)


def test_generate_password_entropy_no_symbols():
    password = passata.generate_password(
        length=None, entropy=128, symbols=False, wordlist=None, force=False)
    assert len(password) == 22


def test_generate_password_entropy_symbols():
    password = passata.generate_password(
        length=None, entropy=128, symbols=True, wordlist=None, force=False)
    assert len(password) == 20


def test_generate_password_short(monkeypatch):
    monkeypatch.setattr(click, 'confirm', lambda m: confirm)
    # Do not confirm
    confirm = False
    with pytest.raises(SystemExit):
        password = passata.generate_password(
            length=4, entropy=None, symbols=True, wordlist=None, force=False)
    # Confirm
    confirm = True
    password = passata.generate_password(
        length=4, entropy=None, symbols=True, wordlist=None, force=False)
    assert len(password) == 4


def test_generate_passphrase(tmpdir):
    words = ['asdf', 'test', 'piou']
    wordlist = tmpdir.join('words')
    wordlist.write('\n'.join(words))
    path = str(wordlist)
    passphrase = passata.generate_password(
        length=5, entropy=None, symbols=True, wordlist=path, force=True)
    passphrase = passphrase.split()
    assert len(passphrase) == 5
    assert all(word in words for word in passphrase)


def test_generate_passphrase_file_not_found(tmpdir):
    wordlist = tmpdir.join('words')
    path = str(wordlist)
    with pytest.raises(SystemExit):
        passata.generate_password(
            length=5, entropy=None, symbols=True, wordlist=path, force=True)


def test_generate(monkeypatch, db):
    monkeypatch.setattr(passata, 'generate_password',
                        lambda l, e, s, w, f: l * 'x')

    # Generate and print
    result = run(['generate'])
    assert result.output == 'xxxxxxxxxxxxxxxxxxxx\n'

    # Generate and put to clipboard
    result = run(['generate', '--clip'])
    assert result.output == ("Put generated password to clipboard. "
                             "Will clear after 45 seconds.\n")
    assert clipboard() == 'xxxxxxxxxxxxxxxxxxxx'

    # Generate, put in new entry and print
    result = run(['generate', 'asdf/test', '--length=5', '--force'])
    assert result.output == 'xxxxx\n'

    # Generate, put in existing entry and put to clipboard
    monkeypatch.setattr(click, 'pause',
                        lambda: print("Press any key to continue ..."))
    result = run(
        ['generate', 'asdf/test', '--length=7', '--force', '--clip'])
    assert result.output == (
        "Put old password to clipboard.\n"
        "Press any key to continue ...\n"
        "Put generated password to clipboard. Will clear after 45 seconds.\n"
    )
    assert clipboard() == 'xxxxxxx'

    assert read(db) == (
        'internet:\n'
        '  github:\n'
        '    password: gh\n'
        '    username: takis\n'
        '  reddit:\n'
        '    password: rdt\n'
        '    username: sakis\n'
        'asdf:\n'
        '  test:\n'
        '    password: xxxxxxx\n'
        '    old_password: xxxxx\n'
    )
