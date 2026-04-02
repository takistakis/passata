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
