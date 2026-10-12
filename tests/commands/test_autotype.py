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

"""Tests for passata autotype."""

import json
import subprocess
from collections.abc import Callable
from typing import Any, NoReturn

import pytest

import passata
from tests.helpers import run


@pytest.fixture(autouse=True)
def linux_backend(monkeypatch: pytest.MonkeyPatch) -> None:
    """Keep existing Linux expectations independent of the test host."""
    monkeypatch.setattr(passata.sys, "platform", "linux")


def test_get_autotype_keys(monkeypatch: pytest.MonkeyPatch) -> None:
    # <autotype> field in entry
    entry = {
        "username": "takis",
        "password": "pass",
        "autotype": "<password> !5 Return",
    }
    autotype = passata.get_autotype_keys(entry)
    assert autotype == ["<password>", "!5", "Return"]

    # <username> and <password> fields in entry
    entry = {"username": "takis", "password": "pass"}
    autotype = passata.get_autotype_keys(entry)
    assert autotype == ["<username>", "Tab", "<password>", "Return"]

    # <password> field in entry
    entry = {"name": "takis", "password": "pass"}
    autotype = passata.get_autotype_keys(entry)
    assert autotype == ["<password>", "Return"]

    # No known fields in entry
    # Suppress notification
    monkeypatch.setattr(passata, "call", lambda _: None)
    entry = {"name": "takis", "pass": "pass"}
    with pytest.raises(SystemExit):
        passata.get_autotype_keys(entry)


@pytest.mark.usefixtures("db")
def test_autotype(monkeypatch: pytest.MonkeyPatch) -> None:
    window_title = "GitHub: The world's leading blah blah blah"
    monkeypatch.setattr(passata, "active_window", lambda: (0, window_title))
    monkeypatch.setattr(passata, "call", print)

    result = run(["autotype"])

    assert result.exception is None
    assert result.output == (
        "['xdotool', 'type', '--clearmodifiers', '--delay', '50', 'takis']\n"
        "['xdotool', 'key', 'Tab']\n"
        "['xdotool', 'type', '--clearmodifiers', '--delay', '50', 'gh']\n"
        "['xdotool', 'key', 'Return']\n"
    )


@pytest.mark.usefixtures("db")
def test_autotype_no_username(monkeypatch: pytest.MonkeyPatch) -> None:
    window_title = "test1"
    monkeypatch.setattr(passata, "active_window", lambda: (0, window_title))
    monkeypatch.setattr(passata, "call", print)
    run(["insert", "autotype/test1", "--password=pass1"])

    result = run(["autotype"])

    assert result.exception is None
    assert result.output == (
        "['xdotool', 'type', '--clearmodifiers', '--delay', '50', 'pass1']\n"
        "['xdotool', 'key', 'Return']\n"
    )


@pytest.mark.usefixtures("db")
def test_autotype_keywords_simple(
    monkeypatch: pytest.MonkeyPatch,
    editor: Callable[[str], None],
) -> None:
    window_title = "A website with the keyword in its title"
    monkeypatch.setattr(passata, "active_window", lambda: (0, window_title))
    monkeypatch.setattr(passata, "call", print)
    # Add a new entry with a single string in keywords
    editor("password: pass2\nkeywords: the keyword\n")
    run(["edit", "autotype/test2"])

    result = run(["autotype"])

    assert result.exception is None
    assert result.output == (
        "['xdotool', 'type', '--clearmodifiers', '--delay', '50', 'pass2']\n"
        "['xdotool', 'key', 'Return']\n"
    )


@pytest.mark.usefixtures("db")
def test_autotype_keywords_complex(
    monkeypatch: pytest.MonkeyPatch,
    editor: Callable[[str], None],
) -> None:
    window_title = "GitHub"
    monkeypatch.setattr(passata, "active_window", lambda: (0, window_title))
    monkeypatch.setattr(passata, "call", print)

    # Add a new entry with an autotype field and a list of
    # strings in keywords that conflict with another entry.
    editor(
        "username: user3\n"
        "password: pass3\n"
        "keywords:\n"
        "- github\n"
        "- yoyoyo\n"
        "autotype: <username> Return !1.5 <password> Return\n",
    )
    run(["edit", "autotype/test3"])

    def fake_out(command: list[str], input_: str | None = None) -> str:
        print("Calling", command)
        print("With input:")
        print(input_)
        print()
        return "autotype/test3"

    # Patch user interaction with dmenu to choose the new entry
    # and sleeping to just print for how long it would sleep.
    monkeypatch.setattr(passata, "out", fake_out)
    monkeypatch.setattr("time.sleep", lambda duration: print("Sleeping for", duration))

    result = run(["autotype"])

    assert result.exception is None
    assert result.output == (
        "Calling ['dmenu']\n"
        "With input:\n"
        "autotype/test3\n"
        "internet/github\n"
        "\n"
        "['xdotool', 'type', '--clearmodifiers', '--delay', '50', 'user3']\n"
        "['xdotool', 'key', 'Return']\n"
        "Sleeping for 1.5\n"
        "['xdotool', 'type', '--clearmodifiers', '--delay', '50', 'pass3']\n"
        "['xdotool', 'key', 'Return']\n"
    )


@pytest.mark.usefixtures("db")
def test_autotype_invalid(
    monkeypatch: pytest.MonkeyPatch,
    editor: Callable[[str], None],
) -> None:
    window_title = "test4"
    monkeypatch.setattr(passata, "active_window", lambda: (0, window_title))
    # Suppress notification
    monkeypatch.setattr(passata, "call", lambda _: None)
    editor("password: pass4\nautotype: <username> Tab <password> Return\n")
    run(["edit", "autotype/test4"])

    result = run(["autotype"])

    assert isinstance(result.exception, SystemExit)


def test_macos_script_stdin(monkeypatch: pytest.MonkeyPatch) -> None:
    captured: list[tuple[list[str], str]] = []

    def fake_run(
        command: list[str],
        **kwargs: object,
    ) -> subprocess.CompletedProcess[str]:
        assert kwargs["capture_output"] is True
        assert kwargs["check"] is True
        assert kwargs["text"] is True
        payload = kwargs["input"]
        assert isinstance(payload, str)
        captured.append((command, payload))
        return subprocess.CompletedProcess(command, 0, stdout="result\n")

    monkeypatch.setattr(passata.subprocess, "run", fake_run)
    text = 'quotes"\\\n and spaces'
    assert passata.macos_autotype("data.text;", {"text": text}) == "result"
    command, payload = captured[0]
    assert command[:4] == ["/usr/bin/osascript", "-l", "JavaScript", "-e"]
    assert command[4].endswith("data.text;")
    assert text not in command[4]
    assert payload is not None
    assert json.loads(payload) == {"text": text}


@pytest.mark.parametrize(
    ("stderr", "expected"),
    [
        (
            "execution error: osascript is not allowed assistive access. (-25211)",
            "Device Control and Data Access (macOS 27)",
        ),
        ("execution error: (-25211)", "WorkflowServiceRunner"),
        ("osascript is not allowed assistive access", "Accessibility"),
        (
            "Not authorized to send Apple events to System Events. (-1743)",
            "Privacy & Security > Automation",
        ),
        ("execution error: Window has changed", "Window has changed"),
        ("execution error: No accessible active window", "No accessible active window"),
        ("", "osascript exited with status 1"),
        (None, "osascript exited with status 1"),
    ],
)
def test_macos_script_failure(
    stderr: str | None,
    expected: str,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def fail(command: list[str], **_: object) -> NoReturn:
        raise subprocess.CalledProcessError(1, command, stderr=stderr)

    monkeypatch.setattr(passata.subprocess, "run", fail)
    with pytest.raises(SystemExit) as exc:
        passata.macos_autotype("data.text;", {"text": "dummy-password"})
    message = str(exc.value)
    assert expected in message
    assert "ObjC.import" not in message
    assert "data.text" not in message
    assert "dummy-password" not in message


def test_macos_script_missing(monkeypatch: pytest.MonkeyPatch) -> None:
    def fail(*_: object, **__: object) -> NoReturn:
        raise FileNotFoundError

    monkeypatch.setattr(passata.subprocess, "run", fail)
    with pytest.raises(SystemExit, match="Executable 'osascript' not found"):
        passata.macos_autotype("data.text;", {})


def test_macos_active_window(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(passata.sys, "platform", "darwin")
    monkeypatch.setattr(
        passata,
        "macos_autotype",
        lambda *_: '["123", "GitHub: Sign in"]',
    )
    assert passata.active_window() == ("123", "GitHub: Sign in")


@pytest.mark.parametrize(
    ("key", "expected"),
    [
        ("Tab", (48, [])),
        ("Return", (36, [])),
        ("shift+Tab", (48, ["shift down"])),
        ("ctrl+alt+Delete", (117, ["control down", "option down"])),
        ("super+a", ("a", ["command down"])),
        ("Command+a", ("a", ["command down"])),
        ("+", ("+", [])),
        ("cmd++", ("+", ["command down"])),
    ],
)
def test_macos_key(key: str, expected: tuple[str | int, list[str]]) -> None:
    assert passata.macos_key(key) == expected


@pytest.mark.parametrize("key", ["F99", "unknown+a", "cmd+", "a+b"])
def test_macos_key_invalid(key: str, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(passata, "call", lambda _: None)
    with pytest.raises(SystemExit):
        passata.macos_key(key)


@pytest.mark.parametrize(
    ("key", "entry", "expected"),
    [
        ("<password>", {"password": 'a"\\\n'}, {"text": 'a"\\\n', "delay": 75}),
        ("<otp>", {"otp": 123456}, {"text": "123456", "delay": 75}),
        ("shift+Tab", {}, {"key": 48, "modifiers": ["shift down"]}),
        ("cmd+a", {}, {"key": "a", "modifiers": ["command down"]}),
    ],
)
def test_macos_keyboard(
    key: str,
    entry: passata.Entry,
    expected: dict[str, Any],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(passata.sys, "platform", "darwin")
    captured: list[tuple[str, dict[str, Any]]] = []
    monkeypatch.setattr(
        passata,
        "macos_autotype",
        lambda script, data: captured.append((script, data)),
    )
    window = ("123", "GitHub")
    passata.keyboard(key, entry, 75, window)
    script, data = captured[0]
    assert data == {**expected, "window": window}
    assert "checkWindow();" in script
    if key.startswith("<"):
        assert script.index("checkWindow();") < script.index("events.keystroke")
        assert "for (const character of data.text)" in script
        assert "delay(data.delay / 1000)" in script


def test_macos_pause(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(passata.sys, "platform", "darwin")
    sleeps: list[float] = []
    monkeypatch.setattr(passata.time, "sleep", sleeps.append)
    passata.keyboard("!0.5", {}, 50)
    assert sleeps == [0.5]


@pytest.mark.usefixtures("db")
def test_macos_autotype(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(passata.sys, "platform", "darwin")
    window = ("123", "GitHub")
    monkeypatch.setattr(passata, "active_window", lambda: window)
    captured: list[dict[str, Any]] = []
    monkeypatch.setattr(
        passata,
        "macos_autotype",
        lambda _, data: captured.append(data),
    )
    result = run(["autotype", "--delay", "75"])
    assert result.exception is None
    assert captured == [
        {"text": "takis", "delay": 75, "window": window},
        {"key": 48, "modifiers": [], "window": window},
        {"text": "gh", "delay": 75, "window": window},
        {"key": 36, "modifiers": [], "window": window},
    ]


@pytest.mark.usefixtures("db")
@pytest.mark.parametrize("selection", ["internet/reddit", None])
def test_macos_native_selection(
    selection: str | None,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(passata.sys, "platform", "darwin")
    window = ("123", "No match")
    monkeypatch.setattr(passata, "active_window", lambda: window)
    choices_seen: list[list[str]] = []
    typed: list[str] = []

    def choose(choices: list[str], target: tuple[str, str]) -> str | None:
        assert target == window
        choices_seen.append(choices)
        return selection

    monkeypatch.setattr(passata, "macos_choose_entry", choose)
    monkeypatch.setattr(
        passata,
        "keyboard",
        lambda key, *_: typed.append(key),
    )
    result = run(["autotype"])
    assert result.exception is None
    assert choices_seen == [["internet/github", "internet/reddit"]]
    assert typed == (["<username>", "Tab", "<password>", "Return"] if selection else [])


@pytest.mark.parametrize("selection", ['"internet/github"', "null"])
def test_macos_choose_entry_script(
    selection: str,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    captured: list[tuple[str, dict[str, Any]]] = []

    def script_run(script: str, data: dict[str, Any]) -> str:
        captured.append((script, data))
        return selection

    monkeypatch.setattr(passata, "macos_autotype", script_run)
    choices = ["internet/github", 'entry with "quotes"']
    window = ("123", "GitHub")
    assert passata.macos_choose_entry(choices, window) == json.loads(selection)
    script, data = captured[0]
    assert data == {"choices": choices, "window": window}
    assert "chooseFromList" in script
    assert script.index("frontmost = true") < script.index("checkWindow();")


@pytest.mark.usefixtures("db")
def test_macos_custom_menu(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(passata.sys, "platform", "darwin")
    monkeypatch.setattr(passata, "active_window", lambda: ("123", "No match"))
    commands: list[list[str]] = []

    def fake_out(command: list[str], input_: str | None = None) -> str:
        assert input_ == "internet/github\ninternet/reddit"
        commands.append(command)
        return "internet/github\n"

    monkeypatch.setattr(passata, "out", fake_out)
    monkeypatch.setattr(passata, "keyboard", lambda *_: None)
    result = run(["autotype", "--menu", "my-menu --flag"])
    assert result.exception is None
    assert commands == [["my-menu", "--flag"]]


@pytest.mark.usefixtures("db")
def test_macos_changed_window(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(passata.sys, "platform", "darwin")
    windows = iter([("123", "GitHub"), ("456", "Other window")])
    monkeypatch.setattr(passata, "active_window", lambda: next(windows))
    monkeypatch.setattr(passata, "call", lambda _: None)
    typed: list[str] = []
    monkeypatch.setattr(passata, "keyboard", lambda key, *_: typed.append(key))
    result = run(["autotype"])
    assert isinstance(result.exception, SystemExit)
    assert typed == []


@pytest.mark.usefixtures("db")
def test_macos_prevalidates_keys(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(passata.sys, "platform", "darwin")
    monkeypatch.setattr(passata, "active_window", lambda: ("123", "GitHub"))
    monkeypatch.setattr(passata, "call", lambda _: None)
    typed: list[str] = []
    monkeypatch.setattr(passata, "keyboard", lambda key, *_: typed.append(key))
    result = run(["autotype", "--sequence", "<username> F99"])
    assert isinstance(result.exception, SystemExit)
    assert typed == []


@pytest.mark.usefixtures("db")
@pytest.mark.parametrize("delay", ["-1", "1.5", "not-a-number"])
def test_autotype_invalid_delay(delay: str) -> None:
    result = run(["autotype", "--delay", delay])
    assert result.exit_code == 2


@pytest.mark.usefixtures("db")
def test_macos_captures_window_before_decrypting(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(passata.sys, "platform", "darwin")
    captured: list[str] = []
    read = passata.DB.read

    def active() -> tuple[str, str]:
        captured.append("window")
        return ("123", "GitHub")

    def read_db(db: passata.DB, lock: bool = False) -> None:
        captured.append("read")
        read(db, lock)

    monkeypatch.setattr(passata, "active_window", active)
    monkeypatch.setattr(passata.DB, "read", read_db)
    monkeypatch.setattr(passata, "keyboard", lambda *_: None)
    result = run(["autotype"])
    assert result.exception is None
    assert captured[:2] == ["window", "read"]


@pytest.mark.usefixtures("db")
def test_autotype_invalid_menu_selection(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(passata, "active_window", lambda: ("123", "No match"))
    monkeypatch.setattr(passata, "out", lambda *_, **__: "missing-entry")
    monkeypatch.setattr(passata, "call", lambda _: None)
    typed: list[str] = []
    monkeypatch.setattr(passata, "keyboard", lambda key, *_: typed.append(key))
    result = run(["autotype"])
    assert isinstance(result.exception, SystemExit)
    assert typed == []


def test_autotype_empty_database(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(passata, "call", lambda _: None)
    with pytest.raises(SystemExit):
        passata.choose_autotype_entry([], [], ("123", "GitHub"), None)
