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

"""Tests for passata edit."""

# ruff: noqa: ARG001
from collections.abc import Callable
from pathlib import Path
from textwrap import dedent

import click
import pytest
import watchdog.events
import watchdog.observers

import passata
from tests.helpers import read, run


class MockObserver:
    """A mock watchdog Observer that captures the scheduled event handler."""

    def __init__(self) -> None:
        """Initialize with no handler."""
        self.handler: watchdog.events.FileSystemEventHandler | None = None

    def schedule(
        self,
        event_handler: watchdog.events.FileSystemEventHandler,
        path: str,  # noqa: ARG002
        recursive: bool = False,  # noqa: ARG002
    ) -> None:
        """Capture the event handler."""
        self.handler = event_handler

    def start(self) -> None:
        """No-op start."""

    def stop(self) -> None:
        """No-op stop."""

    def join(self) -> None:
        """No-op join."""


def test_edit_entry(
    monkeypatch: pytest.MonkeyPatch,
    db: Path,
    editor: Callable,
) -> None:
    monkeypatch.setattr(click, "confirm", lambda _: True)
    editor(
        updated=dedent("""
        username: sakis
        password: yolo
    """),
    )
    run(["edit", "internet/reddit"])
    assert read(db) == dedent("""\
        internet:
          github:
            password: gh
            username: takis
          reddit:
            username: sakis
            password: yolo
    """)


def test_edit_new_entry_in_existing_group(db: Path, editor: Callable) -> None:
    editor(
        updated=dedent("""\
        username: takis
        password: secret
    """),
    )
    result = run(["edit", "internet/stack overflow"])
    assert result.exit_code == 0
    assert result.exception is None
    assert read(db) == dedent("""\
        internet:
          github:
            password: gh
            username: takis
          reddit:
            password: rdt
            username: sakis
          stack overflow:
            username: takis
            password: secret
    """)


def test_edit_new_entry_in_new_group(db: Path, editor: Callable) -> None:
    editor(
        updated=dedent("""\
        username: sakis
        password: yolo
    """),
    )
    run(["edit", "mail/gmail"])
    assert read(db) == dedent("""\
        internet:
          github:
            password: gh
            username: takis
          reddit:
            password: rdt
            username: sakis
        mail:
          gmail:
            username: sakis
            password: yolo
    """)


def test_edit_delete_entry(
    monkeypatch: pytest.MonkeyPatch,
    db: Path,
    editor: Callable,
) -> None:
    editor(updated="")
    # Do not confirm
    monkeypatch.setattr(click, "confirm", lambda _: False)
    result = run(["edit", "internet/reddit"])
    assert result.exit_code == 0
    assert result.exception is None
    assert read(db) == dedent("""\
        internet:
          github:
            password: gh
            username: takis
          reddit:
            password: rdt
            username: sakis
    """)
    passata.unlock_file(db)
    # Confirm
    monkeypatch.setattr(click, "confirm", lambda _: True)
    result = run(["edit", "internet/reddit"])
    assert result.exit_code == 0
    assert result.exception is None
    assert read(db) == dedent("""\
        internet:
          github:
            password: gh
            username: takis
    """)


def test_edit_delete_nonexistent_entry(db: Path, editor: Callable) -> None:
    editor(updated="")
    run(["edit", "asdf/asdf"])
    assert read(db) == dedent("""\
        internet:
          github:
            password: gh
            username: takis
          reddit:
            password: rdt
            username: sakis
    """)


def test_edit_group(
    monkeypatch: pytest.MonkeyPatch,
    db: Path,
    editor: Callable,
) -> None:
    monkeypatch.setattr(click, "confirm", lambda _: True)
    editor(
        updated=dedent("""\
        reddit:
          username: takis
          password: secret
    """),
    )
    run(["edit", "internet"])
    assert read(db) == dedent("""\
        internet:
          reddit:
            username: takis
            password: secret
    """)


def test_edit_delete_group(
    monkeypatch: pytest.MonkeyPatch,
    db: Path,
    editor: Callable,
) -> None:
    editor(updated="")
    # Do not confirm
    monkeypatch.setattr(click, "confirm", lambda _: False)
    run(["edit", "internet"])
    assert read(db) == dedent("""\
        internet:
          github:
            password: gh
            username: takis
          reddit:
            password: rdt
            username: sakis
    """)
    # Confirm
    monkeypatch.setattr(click, "confirm", lambda _: True)
    run(["edit", "internet"])
    assert read(db) == ""


def test_edit_delete_nonexistent_group(db: Path, editor: Callable) -> None:
    editor(updated="")
    run(["edit", "asdf"])
    assert read(db) == dedent("""\
        internet:
          github:
            password: gh
            username: takis
          reddit:
            password: rdt
            username: sakis
    """)


def test_edit_database(
    monkeypatch: pytest.MonkeyPatch,
    db: Path,
    editor: Callable,
) -> None:
    updated = dedent("""\
        internet:
          reddit:
            password: rdt
            username: sakis
    """)
    editor(updated=updated)
    monkeypatch.setattr(click, "confirm", lambda _: True)
    run(["edit"])
    assert read(db) == updated


def test_edit_delete_database(
    monkeypatch: pytest.MonkeyPatch,
    db: Path,
    editor: Callable,
) -> None:
    original = read(db)
    editor(updated="")
    # Do not confirm
    monkeypatch.setattr(click, "confirm", lambda _: False)
    result = run(["edit"])
    assert result.exit_code == 0
    assert result.exception is None
    assert read(db) == original
    passata.unlock_file(db)
    # Confirm
    monkeypatch.setattr(click, "confirm", lambda _: True)
    result = run(["edit"])
    assert result.exit_code == 0
    assert result.exception is None
    assert read(db) == ""


@pytest.mark.usefixtures("db")
def test_edit_invalid_yaml(
    monkeypatch: pytest.MonkeyPatch,
    editor: Callable,
) -> None:
    monkeypatch.setattr(click, "confirm", lambda _: True)
    editor(
        updated=dedent("""\
        username: sakis
        password
    """),
    )
    result = run(["edit", "internet/reddit"])
    assert result.exit_code == 1
    assert isinstance(result.exception, SystemExit)
    assert result.output == "Invalid yaml\n"


def test_edit_no_changes(db: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    def mock_editor(filename: str, editor: str) -> None:
        content = Path(filename).read_text()
        Path(filename).write_text(content)

    monkeypatch.setattr(click, "edit", mock_editor)
    result = run(["edit", "internet/github"])
    assert result.exit_code == 0
    assert result.exception is None
    assert read(db) == dedent("""\
        internet:
          github:
            password: gh
            username: takis
          reddit:
            password: rdt
            username: sakis
    """)


def test_edit_on_modified_saves_changes(
    db: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    mock_observer = MockObserver()
    monkeypatch.setattr(watchdog.observers, "Observer", lambda: mock_observer)

    def mock_editor(filename: str, editor: str) -> None:
        assert mock_observer.handler is not None
        Path(filename).write_text("# internet/github\npassword: newpass\n")
        mock_observer.handler.on_modified(watchdog.events.FileModifiedEvent(filename))

    monkeypatch.setattr(click, "edit", mock_editor)
    run(["edit", "internet/github"])
    assert read(db) == dedent("""\
        internet:
          github:
            password: newpass
          reddit:
            password: rdt
            username: sakis
    """)


def test_edit_on_modified_ignores_different_path(
    db: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    mock_observer = MockObserver()
    monkeypatch.setattr(watchdog.observers, "Observer", lambda: mock_observer)

    def mock_editor(filename: str, editor: str) -> None:
        assert mock_observer.handler is not None
        # Fire event for a completely different file - should be ignored
        other = watchdog.events.FileModifiedEvent(
            str(Path(filename).parent / "unrelated.yml"),
        )
        mock_observer.handler.on_modified(other)
        # Leave the file unchanged so post-editor sees no changes

    monkeypatch.setattr(click, "edit", mock_editor)
    result = run(["edit", "internet/github"])
    assert result.exit_code == 0
    # DB unchanged because event was for a different path
    assert read(db) == dedent("""\
        internet:
          github:
            password: gh
            username: takis
          reddit:
            password: rdt
            username: sakis
    """)


def test_edit_on_modified_ignores_same_content(
    db: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    mock_observer = MockObserver()
    monkeypatch.setattr(watchdog.observers, "Observer", lambda: mock_observer)

    def mock_editor(filename: str, editor: str) -> None:
        assert mock_observer.handler is not None
        # Fire event without changing content - handler exits early at line 985
        mock_observer.handler.on_modified(watchdog.events.FileModifiedEvent(filename))

    monkeypatch.setattr(click, "edit", mock_editor)
    result = run(["edit", "internet/github"])
    assert result.exit_code == 0
    assert read(db) == dedent("""\
        internet:
          github:
            password: gh
            username: takis
          reddit:
            password: rdt
            username: sakis
    """)


def test_edit_on_modified_handles_invalid_yaml(
    db: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    mock_observer = MockObserver()
    monkeypatch.setattr(watchdog.observers, "Observer", lambda: mock_observer)
    monkeypatch.setattr(passata, "send_notification", lambda _: None)

    def mock_editor(filename: str, editor: str) -> None:
        assert mock_observer.handler is not None
        # Write invalid yaml and fire event - handler should notify and return
        original = Path(filename).read_text()
        Path(filename).write_text("username: sakis\npassword\n")
        mock_observer.handler.on_modified(watchdog.events.FileModifiedEvent(filename))
        # Restore original so post-editor sees no net changes
        Path(filename).write_text(original)

    monkeypatch.setattr(click, "edit", mock_editor)
    result = run(["edit", "internet/github"])
    assert result.exit_code == 0


def test_edit_on_modified_ignores_empty_data(
    db: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    mock_observer = MockObserver()
    monkeypatch.setattr(watchdog.observers, "Observer", lambda: mock_observer)

    def mock_editor(filename: str, editor: str) -> None:
        assert mock_observer.handler is not None
        # Temporarily set last_content to force a re-read of empty content
        original = Path(filename).read_text()
        Path(filename).write_text("")
        mock_observer.handler.last_content = None  # type: ignore[attr-defined]
        mock_observer.handler.on_modified(watchdog.events.FileModifiedEvent(filename))
        # Restore original so post-editor sees no net changes
        Path(filename).write_text(original)

    monkeypatch.setattr(click, "edit", mock_editor)
    result = run(["edit", "internet/github"])
    assert result.exit_code == 0
