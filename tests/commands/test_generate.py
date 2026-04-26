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

"""Tests for passata generate."""

import os
import string
import sys
from collections.abc import Generator
from pathlib import Path
from textwrap import dedent

import click
import pytest
from click.testing import Result

import passata
from tests.helpers import clipboard, read, run

ALPHANUMERIC = "abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789"

SYMBOLS = r"""!"#$%&'()*+,-./:;<=>?@[\]^_`{|}~"""


def test_generate_password_charset_alnum() -> None:
    password = passata.generate_password(
        length=10,
        entropy=None,
        charset="alnum",
        wordlist=None,
        force=False,
    )

    assert len(password) == 10
    assert all(char in ALPHANUMERIC for char in password)
    assert not any(char in password for char in SYMBOLS)


def test_generate_password_charset_full() -> None:
    password = passata.generate_password(
        length=17,
        entropy=None,
        charset="full",
        wordlist=None,
        force=False,
    )

    assert len(password) == 17
    assert all(char in ALPHANUMERIC + SYMBOLS for char in password)


def test_generate_password_charset_letters() -> None:
    password = passata.generate_password(
        length=15,
        entropy=None,
        charset="letters",
        wordlist=None,
        force=False,
    )

    assert len(password) == 15
    assert all(char in string.ascii_letters for char in password)


def test_generate_password_charset_digits() -> None:
    password = passata.generate_password(
        length=12,
        entropy=None,
        charset="digits",
        wordlist=None,
        force=False,
    )

    assert len(password) == 12
    assert all(char in string.digits for char in password)


def test_generate_password_entropy_alnum() -> None:
    password = passata.generate_password(
        length=None,
        entropy=128,
        charset="alnum",
        wordlist=None,
        force=False,
    )

    assert len(password) == 22


def test_generate_password_entropy_full() -> None:
    password = passata.generate_password(
        length=None,
        entropy=128,
        charset="full",
        wordlist=None,
        force=False,
    )

    assert len(password) == 20


def test_generate_password_short(monkeypatch: pytest.MonkeyPatch) -> None:
    # Do not confirm
    monkeypatch.setattr(click, "confirm", lambda _: False)

    with pytest.raises(SystemExit):
        password = passata.generate_password(
            length=4,
            entropy=None,
            charset="full",
            wordlist=None,
            force=False,
        )

    # Confirm
    monkeypatch.setattr(click, "confirm", lambda _: True)

    password = passata.generate_password(
        length=4,
        entropy=None,
        charset="full",
        wordlist=None,
        force=False,
    )

    assert len(password) == 4


def test_generate_passphrase(tmp_path: Path) -> None:
    words = ["asdf", "test", "piou"]
    wordpath = tmp_path / "words"
    wordpath.write_text("\n".join(words))

    passphrase = passata.generate_password(
        length=5,
        entropy=None,
        charset="full",
        wordlist=str(wordpath),
        force=True,
    )

    passphrase_parts = passphrase.split()
    assert len(passphrase_parts) == 5
    assert all(word in words for word in passphrase_parts)


def test_generate_passphrase_file_not_found(tmp_path: Path) -> None:
    wordpath = tmp_path / "words"

    with pytest.raises(SystemExit):
        passata.generate_password(
            length=5,
            entropy=None,
            charset="full",
            wordlist=str(wordpath),
            force=True,
        )


def test_generate_passphrase_file_removed_after_resolve(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Test FileNotFoundError when wordlist disappears after resolve."""
    missing = tmp_path / "gone.txt"
    monkeypatch.setattr(passata, "resolve_wordlist", lambda _: missing)

    with pytest.raises(SystemExit, match="No such file or directory"):
        passata.generate_password(
            length=5,
            entropy=None,
            charset="full",
            wordlist="gone",
            force=True,
        )


@pytest.fixture
def patch(monkeypatch: pytest.MonkeyPatch) -> Generator[None, None, None]:
    # NOTE: The following monkeypatch eats the "Generated
    # password with x bits of entropy" message.
    monkeypatch.setattr(
        passata,
        "generate_password",
        lambda length, *_, **__: length * "x",
    )
    monkeypatch.setattr(click, "pause", lambda: print("Press any key to continue ..."))

    # Clear the clipboard before and after the test
    if sys.platform == "darwin":
        input_ = ""
        command = ["pbcopy", "w"]
    else:
        input_ = None
        command = ["xsel", "-c", "-b"]

    passata.out(command, input_=input_)

    yield

    passata.out(command, input_=input_)


def assert_password_in_output(result: Result) -> None:
    assert result.exit_code == 0
    assert result.exception is None
    assert result.output == "xxxxxxxxxxxxxxxxxxxx\n"
    assert clipboard() == ""


def assert_password_in_clipboard(result: Result) -> None:
    assert result.exit_code == 0
    assert result.exception is None
    assert result.output == "Copied generated password to clipboard.\n"
    assert clipboard() == "xxxxxxxxxxxxxxxxxxxx"


def assert_password_in_output_and_clipboard(result: Result) -> None:
    assert result.exit_code == 0
    assert result.exception is None
    assert result.output == dedent("""\
        xxxxxxxxxxxxxxxxxxxx
        Copied generated password to clipboard.
    """)
    assert clipboard() == "xxxxxxxxxxxxxxxxxxxx"


class TestGenerateNoName:
    """Test generate without argument and different print/clip combinations."""

    @pytest.mark.usefixtures("patch", "db")
    def test_generate(self) -> None:
        result = run(["generate"])
        assert_password_in_clipboard(result)

    @pytest.mark.usefixtures("patch", "db")
    def test_generate_clip(self) -> None:
        result = run(["generate", "--clip"])
        assert_password_in_clipboard(result)

    @pytest.mark.usefixtures("patch", "db")
    def test_generate_no_clip(self) -> None:
        result = run(["generate", "--no-clip"])
        assert_password_in_output(result)

    @pytest.mark.usefixtures("patch", "db")
    def test_generate_print(self) -> None:
        result = run(["generate", "--print"])
        assert_password_in_output_and_clipboard(result)

    @pytest.mark.usefixtures("patch", "db")
    def test_generate_no_print(self) -> None:
        result = run(["generate", "--no-print"])
        assert_password_in_clipboard(result)

    @pytest.mark.usefixtures("patch", "db")
    def test_generate_print_clip(self) -> None:
        result = run(["generate", "--print", "--clip"])
        assert_password_in_output_and_clipboard(result)

    @pytest.mark.usefixtures("patch", "db")
    def test_generate_print_no_clip(self) -> None:
        result = run(["generate", "--print", "--no-clip"])
        assert_password_in_output(result)

    @pytest.mark.usefixtures("patch", "db")
    def test_generate_no_print_clip(self) -> None:
        result = run(["generate", "--no-print", "--clip"])
        assert_password_in_clipboard(result)

    @pytest.mark.usefixtures("patch", "db")
    def test_generate_no_print_no_clip(self) -> None:
        result = run(["generate", "--no-print", "--no-clip"])
        assert_password_in_output(result)


@pytest.mark.usefixtures("patch")
def test_generate_put_in_new_entry_print(db: Path) -> None:
    result = run(["generate", "asdf/test", "--print", "--no-clip"])
    assert_password_in_output(result)
    assert read(db) == dedent("""\
        internet:
          github:
            password: gh
            username: takis
          reddit:
            password: rdt
            username: sakis
        asdf:
          test:
            password: xxxxxxxxxxxxxxxxxxxx
    """)


@pytest.mark.usefixtures("patch")
def test_generate_put_in_existing_entry_clip(db: Path) -> None:
    result = run(["generate", "internet/github", "--force"])

    assert result.exit_code == 0
    assert result.exception is None
    assert result.output == dedent("""\
        Copied old password to clipboard.
        Press any key to continue ...
        Copied generated password to clipboard.
    """)
    assert clipboard() == "xxxxxxxxxxxxxxxxxxxx"
    assert read(db) == dedent("""\
        internet:
          github:
            password: xxxxxxxxxxxxxxxxxxxx
            username: takis
            old_password: gh
          reddit:
            password: rdt
            username: sakis
    """)


class TestResolveWordlist:
    """Test resolve_wordlist function."""

    def test_existing_file_path(self, tmp_path: Path) -> None:
        """Test that an existing file path is returned as-is."""
        wordpath = tmp_path / "wordlist.txt"
        wordpath.write_text("word1\nword2\n")
        assert passata.resolve_wordlist(str(wordpath)) == wordpath

    def test_name_resolved_in_directory(
        self,
        tmp_path: Path,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """Test that a wordlist name is resolved from known directories."""
        (tmp_path / "bip39.txt").write_text("word1\nword2\n")
        monkeypatch.setattr(passata, "WORDLIST_DIRS", [tmp_path])
        assert passata.resolve_wordlist("bip39") == tmp_path / "bip39.txt"

    def test_name_not_found(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """Test that the function exits if the wordlist is not found."""
        monkeypatch.setattr(passata, "WORDLIST_DIRS", [])
        with pytest.raises(SystemExit) as cm:
            passata.resolve_wordlist("nonexistent")
        assert "not found" in str(cm.value)


class TestAvailableWordlists:
    """Test available_wordlists function."""

    def test_lists_wordlists(
        self,
        tmp_path: Path,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """Test that available wordlists are listed."""
        (tmp_path / "bip39.txt").write_text("word1\n")
        (tmp_path / "eff_large_wordlist.txt").write_text("word1\n")
        monkeypatch.setattr(passata, "WORDLIST_DIRS", [tmp_path])
        names = passata.available_wordlists()
        assert "bip39" in names
        assert "eff_large_wordlist" in names

    def test_empty_when_no_dirs(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """Test that an empty list is returned when no directories exist."""
        monkeypatch.setattr(passata, "WORDLIST_DIRS", [Path("/nonexistent")])
        assert passata.available_wordlists() == []


@pytest.mark.usefixtures("patch")
def test_generate_length_overrides_config_entropy(db: Path) -> None:  # noqa: ARG001
    """When entropy is from config and length is on CLI, length takes precedence."""
    confpath = Path(os.environ["PASSATA_CONFIG_PATH"])
    confpath.write_text(confpath.read_text() + "generate:\n  entropy: 128\n")
    result = run(["generate", "--length", "10", "--no-clip"])
    assert result.exit_code == 0
    assert result.exception is None
    assert result.output == "xxxxxxxxxx\n"


@pytest.mark.usefixtures("patch")
def test_generate_charset_overrides_config_wordlist(db: Path) -> None:  # noqa: ARG001
    """When wordlist is from config and charset is on CLI, charset takes precedence."""
    confpath = Path(os.environ["PASSATA_CONFIG_PATH"])
    confpath.write_text(confpath.read_text() + "generate:\n  wordlist: eff\n")
    result = run(["generate", "--charset", "alnum", "--no-clip"])
    assert result.exit_code == 0
    assert result.exception is None
    assert result.output == "xxxxxxxxxxxxxxxxxxxx\n"
