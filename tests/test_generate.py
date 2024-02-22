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

import sys
from textwrap import dedent

import click
import pytest

import passata
from tests.helpers import clipboard, read, run

ALPHANUMERIC = "abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789"

SYMBOLS = r"""!"#$%&'()*+,-./:;<=>?@[\]^_`{|}~"""


def test_generate_password_length_no_symbols():
    password = passata.generate_password(
        length=10, entropy=None, symbols=False, words=False, wordpath="", force=False
    )

    assert len(password) == 10
    assert all(char in ALPHANUMERIC for char in password)
    assert not any(char in password for char in SYMBOLS)


def test_generate_password_length_symbols():
    password = passata.generate_password(
        length=17, entropy=None, symbols=True, words=False, wordpath="", force=False
    )

    assert len(password) == 17
    assert all(char in ALPHANUMERIC + SYMBOLS for char in password)


def test_generate_password_entropy_no_symbols():
    password = passata.generate_password(
        length=None,
        entropy=128,
        symbols=False,
        words=False,
        wordpath="",
        force=False,
    )
    assert len(password) == 22


def test_generate_password_entropy_symbols():
    password = passata.generate_password(
        length=None,
        entropy=128,
        symbols=True,
        words=False,
        wordpath="",
        force=False,
    )
    assert len(password) == 20


def test_generate_password_short(monkeypatch):
    monkeypatch.setattr(click, "confirm", lambda _: confirm)
    # Do not confirm
    confirm = False
    with pytest.raises(SystemExit):
        password = passata.generate_password(
            length=4,
            entropy=None,
            symbols=True,
            words=False,
            wordpath="",
            force=False,
        )
    # Confirm
    confirm = True
    password = passata.generate_password(
        length=4, entropy=None, symbols=True, words=False, wordpath="", force=False
    )
    assert len(password) == 4


def test_generate_passphrase(tmpdir):
    words = ["asdf", "test", "piou"]
    wordpath = tmpdir.join("words")
    wordpath.write("\n".join(words))
    path = str(wordpath)
    passphrase = passata.generate_password(
        length=5,
        entropy=None,
        symbols=True,
        words=True,
        wordpath=path,
        force=True,
    )
    passphrase = passphrase.split()
    assert len(passphrase) == 5
    assert all(word in words for word in passphrase)


def test_generate_passphrase_file_not_found(tmpdir):
    wordpath = tmpdir.join("words")
    path = str(wordpath)
    with pytest.raises(SystemExit):
        passata.generate_password(
            length=5,
            entropy=None,
            symbols=True,
            words=True,
            wordpath=path,
            force=True,
        )


@pytest.fixture
def patch(monkeypatch):
    def generate_password(length, *args, **kwargs):
        return length * "x"

    # NOTE: The following monkeypatch eats the "Generated
    # password with x bits of entropy" message.
    monkeypatch.setattr(passata, "generate_password", generate_password)
    monkeypatch.setattr(click, "pause", lambda: print("Press any key to continue ..."))
    # Clear the clipboard before and after the test
    if sys.platform == "darwin":
        input = ""
        command = ["pbcopy", "w"]
    else:
        input = None
        command = ["xsel", "-c", "-b"]
    passata.out(command, input=input)
    yield
    passata.out(command, input=input)


def assert_password_in_output(result):
    assert result.exit_code == 0
    assert result.exception is None
    assert result.output == "xxxxxxxxxxxxxxxxxxxx\n"
    assert clipboard() == ""


def assert_password_in_clipboard(result):
    assert result.exit_code == 0
    assert result.exception is None
    assert result.output == "Copied generated password to clipboard.\n"
    assert clipboard() == "xxxxxxxxxxxxxxxxxxxx"


def assert_password_in_output_and_clipboard(result):
    assert result.exit_code == 0
    assert result.exception is None
    assert result.output == dedent(
        """\
        xxxxxxxxxxxxxxxxxxxx
        Copied generated password to clipboard.
        """
    )
    assert clipboard() == "xxxxxxxxxxxxxxxxxxxx"


class TestGenerateNoName:
    """Test generate without argument and different print/clip combinations."""

    def test_generate(self, patch, db):
        result = run(["generate"])
        assert_password_in_clipboard(result)

    def test_generate_clip(self, patch, db):
        result = run(["generate", "--clip"])
        assert_password_in_clipboard(result)

    def test_generate_no_clip(self, patch, db):
        result = run(["generate", "--no-clip"])
        assert_password_in_output(result)

    def test_generate_print(self, patch, db):
        result = run(["generate", "--print"])
        assert_password_in_output_and_clipboard(result)

    def test_generate_no_print(self, patch, db):
        result = run(["generate", "--no-print"])
        assert_password_in_clipboard(result)

    def test_generate_print_clip(self, patch, db):
        result = run(["generate", "--print", "--clip"])
        assert_password_in_output_and_clipboard(result)

    def test_generate_print_no_clip(self, patch, db):
        result = run(["generate", "--print", "--no-clip"])
        assert_password_in_output(result)

    def test_generate_no_print_clip(self, patch, db):
        result = run(["generate", "--no-print", "--clip"])
        assert_password_in_clipboard(result)

    def test_generate_no_print_no_clip(self, patch, db):
        result = run(["generate", "--no-print", "--no-clip"])
        assert_password_in_output(result)


def test_generate_put_in_new_entry_print(patch, db):
    result = run(["generate", "asdf/test", "--print", "--no-clip"])
    assert_password_in_output(result)
    assert read(db) == dedent(
        """\
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
        """
    )


def test_generate_put_in_existing_entry_clip(patch, db):
    result = run(["generate", "internet/github", "--force"])
    assert result.exit_code == 0
    assert result.exception is None
    assert result.output == dedent(
        """\
        Copied old password to clipboard.
        Press any key to continue ...
        Copied generated password to clipboard.
        """
    )
    assert clipboard() == "xxxxxxxxxxxxxxxxxxxx"
    assert read(db) == dedent(
        """\
        internet:
          github:
            password: xxxxxxxxxxxxxxxxxxxx
            username: takis
            old_password: gh
          reddit:
            password: rdt
            username: sakis
        """
    )


class TestGetWordpath:
    """Test get_wordpath function."""

    def test_wordpath_not_none(self):
        """
        Test that the function returns the provided wordpath if it's not None.
        """
        wordpath = "/path/to/wordlist.txt"
        assert passata.get_wordpath(wordpath) == wordpath

    def test_wordpath_in_directories(self, monkeypatch):
        """
        Test that the function returns the wordpath if it exists in one of the
        directories.
        """
        monkeypatch.setattr("os.path.exists", lambda x: True)
        wordpath = passata.get_wordpath(None)
        assert wordpath.endswith("eff_large_wordlist.txt")
        assert any(
            wordpath.startswith(directory)
            for directory in [
                "/usr/local/share/passata",
                "/usr/share/passata",
            ]
        )

    def test_wordpath_not_found(self, monkeypatch):
        """
        Test that the function exits if the wordpath is not found in any of the
        directories.
        """
        monkeypatch.setattr("os.path.exists", lambda x: False)
        with pytest.raises(SystemExit) as cm:
            passata.get_wordpath(None)

        assert str(cm.value) == "--words option requires a wordpath"
