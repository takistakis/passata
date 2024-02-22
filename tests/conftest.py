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

"""The passata test suite conftest file."""

import os
from textwrap import dedent

import click
import pytest

import passata


@pytest.fixture
def db(tmpdir, monkeypatch):
    monkeypatch.setattr(passata.DB, "encrypt", lambda s, x, g: x)
    monkeypatch.setattr(passata.DB, "decrypt", lambda s, x: open(x).read())

    confpath = tmpdir.join("config.yml")
    dbpath = tmpdir.join("passata.db")

    confpath.write(
        dedent(
            f"""\
            database: {dbpath}
            gpg_id: mail@mail.com
            """
        )
    )

    dbpath.write(
        dedent(
            """\
            internet:
              github:
                password: gh
                username: takis
              reddit:
                password: rdt
                username: sakis
            """
        )
    )

    os.environ["PASSATA_CONFIG_PATH"] = str(confpath)

    yield dbpath


@pytest.fixture
def editor(monkeypatch):
    def make_editor(updated):
        def mock_editor(filename, editor):
            with open(filename, "w") as f:
                f.write(updated)

        monkeypatch.setattr(click, "edit", mock_editor)

    return make_editor
