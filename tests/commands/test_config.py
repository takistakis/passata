# Copyright 2026 Panagiotis Ktistakis <panktist@gmail.com>
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

from pathlib import Path
from unittest.mock import patch

import pytest

from tests.helpers import run


@pytest.mark.usefixtures("db")
def test_config(tmp_path: Path) -> None:
    test_editor = "nano"

    with patch("passata.click.edit") as mock_edit:
        result = run(["config", "--editor", test_editor])

        assert result.exit_code == 0
        mock_edit.assert_called_once_with(
            filename=str(tmp_path / "config.yml"),
            editor=test_editor,
        )
