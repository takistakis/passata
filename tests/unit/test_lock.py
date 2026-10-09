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

import fcntl
from pathlib import Path
from threading import Thread

import click
import pytest

import passata
from tests.helpers import run


def test_lock_is_exclusive_and_release_preserves_inode(tmp_path: Path) -> None:
    path = tmp_path / "database.gpg"
    lockpath = path.with_suffix(".lock")
    with passata.lock_file(path) as first:
        inode = lockpath.stat().st_ino
        with pytest.raises(SystemExit, match="Another passata process"):
            passata.lock_file(path)
        assert not first.closed

    assert lockpath.stat().st_ino == inode
    with lockpath.open("a") as waiting, passata.lock_file(path) as second:
        assert not second.closed
        with pytest.raises(BlockingIOError):
            fcntl.flock(waiting, fcntl.LOCK_EX | fcntl.LOCK_NB)
    assert lockpath.stat().st_ino == inode


def test_lock_open_failure_is_reported(tmp_path: Path) -> None:
    with pytest.raises(SystemExit, match="Couldn't open lock file"):
        passata.lock_file(tmp_path / "missing-directory" / "database.gpg")


def test_read_only_command_does_not_acquire_writer_lock(db: Path) -> None:
    with passata.lock_file(db):
        result = run(["show", "internet/github"])
    assert result.exit_code == 0
    assert "password: gh" in result.output


def test_writer_lock_is_released_on_error(db: Path) -> None:
    result = run(["mv", "missing", "new"])
    assert result.exit_code == 1
    with passata.lock_file(db) as lock:
        assert not lock.closed


def test_post_write_hook_runs_after_clipboard_with_lock_held(
    db: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    events = []
    monkeypatch.setattr(
        passata,
        "to_clipboard",
        lambda *_, **__: events.append("clipboard"),
    )
    monkeypatch.setattr(click, "pause", lambda: None)

    def hook(database: passata.DB) -> None:
        assert database.path == db
        with pytest.raises(SystemExit, match="Another passata process"):
            passata.lock_file(db)
        events.append("hook")

    monkeypatch.setattr(passata.DB, "execute_post_write_hook", hook)
    result = run(["generate", "internet/github", "--force"])

    assert result.exit_code == 0
    assert events == ["clipboard", "clipboard", "hook"]
    with passata.lock_file(db) as lock:
        assert not lock.closed


def test_watcher_write_uses_command_context_for_hook(
    db: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    events = []

    def hook(database: passata.DB) -> None:
        assert database.path == db
        with pytest.raises(SystemExit, match="Another passata process"):
            passata.lock_file(db)
        events.append("hook")

    monkeypatch.setattr(passata.DB, "execute_post_write_hook", hook)
    with click.Context(passata.cli, obj={}) as context:
        database = passata.DB(db)
        database.db = {"entry": {"password": "value"}}
        with click.Context(passata.edit, parent=context):
            lock = passata.lock_file(db)
            thread = Thread(target=database.write, args=("unused",))
            thread.start()
            thread.join(timeout=5)
            assert not thread.is_alive()
        assert not lock.closed
        assert events == []
    assert events == ["hook"]
    assert lock.closed


def test_post_write_hook_failure_is_reported_without_changing_status(
    db: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def hook(database: passata.DB) -> None:
        assert database.path == db
        passata.sys.exit("Post-write hook failed")

    monkeypatch.setattr(passata.DB, "execute_post_write_hook", hook)
    result = run(["rm", "--force", "internet/reddit"])

    assert result.exit_code == 0
    assert result.output == "Post-write hook failed\n"
    assert "reddit" not in db.read_text()
    with passata.lock_file(db) as lock:
        assert not lock.closed
