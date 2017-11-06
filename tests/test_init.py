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

"""Tests for passata init."""

import os.path

import click

import passata
from tests.helpers import run


def test_init(tmpdir, monkeypatch):
    monkeypatch.setattr(passata.DB, 'encrypt', lambda s, x: x)
    monkeypatch.setattr(passata.DB, 'decrypt', lambda s, x: open(x).read())

    confpath = tmpdir.join('config.yml')
    dbpath = tmpdir.join('passata.db')

    # Try to execute a command without having initialized passata
    result = run(['--config', str(confpath), 'ls'])
    assert isinstance(result.exception, SystemExit)
    assert result.output == "Run `passata init` first\n"
    assert not os.path.isfile(str(dbpath))

    # Initialize. It should not ask for confirmation.
    email = 'mail@mail.com'
    result = run(['--config=%s' % str(confpath), 'init',
                  '--gpg-id=%s' % email, '--path=%s' % dbpath])
    assert result.exit_code == 0
    assert result.exception is None
    assert result.output == ''
    assert os.path.isfile(str(dbpath))
    contents = confpath.read()
    assert 'database: %s' % dbpath in contents
    assert 'gpg_id: %s' % email in contents

    # Initialize again. Now it should ask for confirmation.
    monkeypatch.setattr(click, 'confirm', lambda m: confirm)
    confirm = False
    email2 = 'anothermail@mail.com'
    result = run(['--config=%s' % str(confpath), 'init',
                  '--gpg-id=%s' % email2, '--path=%s' % dbpath])
    contents = confpath.read()
    assert 'gpg_id: %s' % email in contents
    assert 'gpg_id: %s' % email2 not in contents

    # Try to execute a command again and now it should work
    result = run(['--config', str(confpath), 'ls'])
    assert result.exit_code == 0
    assert result.exception is None
    assert result.output == ''

    # Try again after deleting the database and it should fail
    os.unlink(str(dbpath))
    result = run(['--config', str(confpath), 'ls'])
    assert isinstance(result.exception, SystemExit)
    assert result.output == "Database file (%s) does not exist\n" % dbpath
