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

import pytest

import passata
from tests.helpers import run


@pytest.fixture
def cryptopatch(monkeypatch):
    monkeypatch.setattr(passata.DB, 'encrypt', lambda s, x, g: x)
    monkeypatch.setattr(passata.DB, 'decrypt', lambda s, x: open(x).read())


def assert_db_full():
    result = run(['ls'])
    assert result.exit_code == 0
    assert result.exception is None
    assert result.output == (
        'internet\n'
        '├── github\n'
        '└── reddit\n'
    )


def assert_db_empty():
    result = run(['ls'])
    assert result.exit_code == 0
    assert result.exception is None
    assert result.output == ''


def test_command_uninitialized(tmpdir, cryptopatch):
    confpath = tmpdir.join('config.yml')
    dbpath = tmpdir.join('passata.db')

    result = run(['--config', str(confpath), 'ls'])
    assert isinstance(result.exception, SystemExit)
    assert result.output == "Run `passata init` first\n"
    assert not os.path.isfile(str(dbpath))


def test_init_uninitialized(tmpdir, cryptopatch):
    confpath = tmpdir.join('config.yml')
    dbpath = tmpdir.join('passata.db')

    # Initialize. It should not ask for confirmation.
    gpg_id = 'mail@mail.com'
    result = run([
        '--config=%s' % str(confpath),
        'init',
        '--gpg-id=%s' % gpg_id,
        '--path=%s' % dbpath,
    ])
    assert result.exit_code == 0
    assert result.exception is None
    assert result.output == ''
    assert os.path.isfile(str(dbpath))
    contents = confpath.read()
    assert 'database: %s' % dbpath in contents
    assert 'gpg_id: %s' % gpg_id in contents

    # Try to execute a command again and now it should work
    result = run(['--config', str(confpath), 'ls'])
    assert result.exit_code == 0
    assert result.exception is None
    assert result.output == ''


def test_command_initialized_deleted_db(db):
    os.unlink(str(db))
    result = run(['ls'])
    assert isinstance(result.exception, SystemExit)
    assert result.output == "Database file (%s) does not exist\n" % db


def test_init_initialized_do_not_confirm(db):
    confpath = os.environ['PASSATA_CONFIG_PATH']

    assert_db_full()

    gpg_id = 'anothermail@mail.com'
    cmd = [
        '--config=%s' % confpath,
        'init',
        '--gpg-id=%s' % gpg_id,
        '--path=%s' % db,
    ]
    result = run(cmd, input='n\n')
    assert result.exit_code == 0
    assert result.exception is None
    assert result.output == 'Overwrite %s? [y/N]: n\n' % confpath
    with open(confpath) as f:
        contents = f.read()
    assert 'gpg_id: mail@mail.com' in contents
    assert 'gpg_id: %s' % gpg_id not in contents

    assert_db_full()


def test_init_initialized_confirm_only_config(db):
    confpath = os.environ['PASSATA_CONFIG_PATH']

    assert_db_full()

    gpg_id = 'anothermail@mail.com'
    cmd = [
        '--config=%s' % confpath,
        'init',
        '--gpg-id=%s' % gpg_id,
        '--path=%s' % db,
    ]
    result = run(cmd, input='y\nn\n')
    assert result.exit_code == 0
    assert result.exception is None
    assert result.output == (
        'Overwrite %s? [y/N]: y\n'
        'Overwrite %s? [y/N]: n\n' % (confpath, db)
    )
    with open(confpath) as f:
        contents = f.read()
    assert 'gpg_id: mail@mail.com' not in contents
    assert 'gpg_id: %s' % gpg_id in contents

    assert_db_full()


def test_init_initialized_confirm_all(db, monkeypatch):
    confpath = os.environ['PASSATA_CONFIG_PATH']

    assert_db_full()

    gpg_id = 'anothermail@mail.com'
    cmd = [
        '--config=%s' % confpath,
        'init',
        '--gpg-id=%s' % gpg_id,
        '--path=%s' % db,
    ]
    result = run(cmd, input='y\ny\n')
    assert result.exit_code == 0
    assert result.exception is None
    assert result.output == (
        'Overwrite %s? [y/N]: y\n'
        'Overwrite %s? [y/N]: y\n' % (confpath, db)
    )
    with open(confpath) as f:
        contents = f.read()
    assert 'gpg_id: mail@mail.com' not in contents
    assert 'gpg_id: %s' % gpg_id in contents

    assert_db_empty()
