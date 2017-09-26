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

import time

import click
import py
import pytest

import passata
from tests.helpers import run


def test_invalid_call():
    with pytest.raises(SystemExit):
        passata.call(['there_is_no_such_executable.exe'])


def test_lock(monkeypatch, db):

    class FakeContext:
        obj = {'database': str(db)}

    ctx = FakeContext()
    monkeypatch.setattr(click, 'get_current_context', lambda: ctx)

    def background_lock():
        passata.lock_file(str(db))
        assert '_lock' in ctx.obj
        time.sleep(1)

    # lockf locks are bound to processes, not file descriptors
    # so we have to use a forked process to properly test this.
    ff = py.process.ForkedFunc(background_lock)
    time.sleep(0.5)

    result = run(['rm', 'internet/github', '--force'])
    assert result.output == "Another passata process is editing the database\n"
    assert repr(result.exception) == 'SystemExit(1,)'

    result = ff.waitfinish()
    assert result.exitstatus == 0
    assert result.out == result.err == ''

    result = run(['rm', 'internet/github', '--force'])
    assert result.output == ''
    assert result.exception is None
