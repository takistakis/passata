from typing import Any
from unittest.mock import MagicMock, Mock, patch

import pytest

from passata import DB


class TestHooks:
    """Test that the pre-read and post-write hooks are executed correctly."""

    @patch("passata.call")
    def test_execute_pre_read_hook_with_hook(self, mock_call: MagicMock) -> None:
        hook = Mock()
        db: DB = DB(None)
        db.pre_read_hook = hook

        db.execute_pre_read_hook()

        mock_call.assert_called_once_with(hook)

    @patch("passata.call")
    def test_execute_pre_read_hook_without_hook(self, mock_call: MagicMock) -> None:
        db: DB = DB(None)
        db.pre_read_hook = None

        db.execute_pre_read_hook()

        mock_call.assert_not_called()

    @patch("passata.call")
    def test_execute_post_write_hook_with_hook(self, mock_call: MagicMock) -> None:
        hook = Mock()
        db: DB = DB(None)
        db.post_write_hook = hook

        db.execute_post_write_hook()

        mock_call.assert_called_once_with(hook)

    @patch("passata.call")
    def test_execute_post_write_hook_without_hook(self, mock_call: MagicMock) -> None:
        db: DB = DB(None)
        db.post_write_hook = None

        db.execute_post_write_hook()

        mock_call.assert_not_called()


class TestValidate:
    """Test the validate method of the DB class."""

    @staticmethod
    def make_db_with_structure(structure: dict[str, Any]) -> DB:
        db = DB(path=None)
        db.db = structure
        return db

    def test_validate_valid_db(self) -> None:
        db = self.make_db_with_structure(
            {
                "group1": {
                    "entry1": {"foo": "bar"},
                    "entry2": {"baz": "qux"},
                },
                "group2": {
                    "entry3": {"hello": "world"},
                },
            },
        )
        db.validate()  # Should not raise

    def test_validate_non_dict_db(self) -> None:
        db = self.make_db_with_structure(
            ["not", "a", "dict"],  # type: ignore[arg-type]
        )
        with pytest.raises(SystemExit, match="Database is not a dict"):
            db.validate()

    def test_validate_group_not_dict(self) -> None:
        db = self.make_db_with_structure(
            {
                "group1": ["not", "a", "dict"],
            },
        )
        with pytest.raises(SystemExit, match="Group 'group1' is not a dict"):
            db.validate()

    def test_validate_entry_not_dict(self) -> None:
        db = self.make_db_with_structure(
            {
                "group1": {
                    "entry1": "not a dict",
                },
            },
        )
        with pytest.raises(SystemExit, match="Entry 'entry1' is not a dict"):
            db.validate()
