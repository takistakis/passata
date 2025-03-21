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
from pathlib import Path
from textwrap import dedent
from typing import Callable, Generator

import click
import pytest

import passata


@pytest.fixture
def db(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Generator[Path, None, None]:
    monkeypatch.setattr(passata.DB, "encrypt", lambda s, x, g: x)
    monkeypatch.setattr(passata.DB, "decrypt", lambda s, x: open(x).read())

    confpath = tmp_path / "config.yml"
    dbpath = tmp_path / "passata.db"

    confpath.write_text(
        dedent(
            f"""\
            database: {dbpath}
            gpg_id: mail@mail.com
            """
        )
    )

    dbpath.write_text(
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
def editor(
    monkeypatch: pytest.MonkeyPatch,
) -> Generator[Callable[[str], None], None, None]:
    def make_editor(updated: str) -> None:
        def mock_editor(filename: str, editor: str) -> None:
            with open(filename, "w") as f:
                f.write(updated)

        monkeypatch.setattr(click, "edit", mock_editor)

    yield make_editor
