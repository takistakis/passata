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

"""Tests for passata utility functions."""

import multiprocessing
import textwrap
import time

import pytest

import passata
from tests.helpers import run


def test_non_zero_exit_status():
    with pytest.raises(SystemExit):
        passata.call(["false"])


def test_command_not_found():
    with pytest.raises(SystemExit):
        passata.call(["there_is_no_such_executable.exe"])


def background_lock(db):
    # Assign the lock to a variable to keep it in scope and prevent the file
    # from closing.
    lock = passata.lock_file(str(db))  # noqa
    time.sleep(1)


def test_lock(monkeypatch, db):
    # lockf locks are bound to processes, not file descriptors
    # so we have to use a forked process to properly test this.
    process = multiprocessing.Process(target=background_lock, args=(db,))
    process.start()
    time.sleep(0.5)

    result = run(["rm", "internet/github", "--force"])
    assert isinstance(result.exception, SystemExit)
    assert result.output == "Another passata process is editing the database\n"

    result = process.join()

    result = run(["rm", "internet/github", "--force"])
    assert result.output == ""
    assert result.exception is None

    try:
        # The file is normally unlocked and deleted when the
        # program exits (see: atexit), which hasn't happened yet.
        # The first time we call unlock_file, we explicitly unlock it.
        passata.unlock_file(str(db))
        # The second, we do nothing but no error is raised
        # either, because we ignore any FileNotFoundError.
        passata.unlock_file(str(db))
    except Exception as e:
        pytest.fail(f"unlock_file: {e}")


def test_default_gpg_id(monkeypatch):
    monkeypatch.setattr(passata, "out", lambda cmd: output)
    output = textwrap.dedent(
        """\
        /home/user/.gnupg/pubring.kbx
        ------------------------------
        sec   rsa4096 2015-02-26 [SC] [expires: 2018-12-20]
            0123456789ABCDEF0123456789ABCDEF01234567
        uid           [ultimate] Name Surname <mail@mail.com>
        ssb   rsa4096 2015-02-26 [E] [expires: 2018-12-20]

        sec   rsa4096 2016-01-1 [SC] [expires: 2018-1-1]
            0123456789ABCDEF0123456789ABCDEF01234567
        uid           [ultimate] Name Surname <mail2@mail.com>
        ssb   rsa4096 2016-01-1 [E] [expires: 2018-1-1]"""
    )
    assert passata.default_gpg_id() == "mail@mail.com"
    # No secret keys
    output = ""
    with pytest.raises(SystemExit):
        passata.default_gpg_id()


def test_keywords(db):
    db = passata.DB(str(db))

    # The `keywords` field is empty
    db.put(
        "internet/reddit",
        {
            "username": "takis",
            "password": "pass",
        },
    )
    assert db.keywords("internet/reddit") == []

    # The `keywords` field contains a string
    db.put(
        "internet/reddit",
        {"username": "takis", "password": "pass", "keywords": "Keyword"},
    )
    assert db.keywords("internet/reddit") == ["keyword"]

    # The `keywords` field contains a list of strings
    db.put(
        "internet/reddit",
        {
            "username": "takis",
            "password": "pass",
            "keywords": ["Google", "YouTube", "Gmail"],
        },
    )
    assert db.keywords("internet/reddit") == ["google", "youtube", "gmail"]
