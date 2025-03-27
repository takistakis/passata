#!/usr/bin/env python3

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

"""A simple password manager, inspired by pass."""

from __future__ import annotations

import atexit
import fcntl
import math
import os
import random
import re
import shlex
import string
import subprocess
import sys
import tempfile
import time
from pathlib import Path
from typing import Any, Iterator, Sequence, TextIO

import click
import watchdog.events
import watchdog.observers
import yaml
import yaml.scanner

__version__ = "0.2.0"


Obj = dict[str, Any]
Config = dict[str, Any]
Entry = dict[str, Any]
Group = dict[str, Entry]
Database = dict[str, Group]


# Utilities
def call(
    command: Path | list[str],
    stdout: int | None = None,
    input: str | None = None,
) -> str:
    """Run command, optionally passing `input` to stdin.

    By default, standard output is printed and ignored and None is returned.
    Setting stdout=subprocess.PIPE, will capture and return standard output
    instead.
    """
    try:
        return subprocess.run(
            command,
            input=input if input is None else str(input),
            stdout=stdout,
            stderr=subprocess.DEVNULL,
            check=True,
            universal_newlines=True,
        ).stdout
    except subprocess.CalledProcessError as e:
        sys.exit(str(e))
    except FileNotFoundError:
        path = command[0] if isinstance(command, list) else command
        sys.exit(f"Executable '{path}' not found")


def out(command: list[str], input: str | None = None) -> str:
    """Run command, optionally passing `input` to stdin, and return output.

    The output usually comes back with a trailing newline and it needs to be
    striped if not needed.
    """
    return call(command, stdout=subprocess.PIPE, input=input)


def echo(data: str) -> None:
    """Print data to stdout or via a pager if it doesn't fit on screen."""
    # Bright blue key (color 12) and bright yellow colon (color 11).
    # Colors are applied manually using ANSI escape codes because
    # click.style does not support bright colors. The key ends at the
    # first colon that is followed by either a space or a newline.
    data = re.sub(
        r"(^\s*.*?):(\s)",
        r"\033[38;5;12m\1\033[38;5;11m:\033[0m\2",
        data,
        flags=re.MULTILINE,
    )
    data = re.sub(
        r"(^\s*-\s)",
        r"\033[38;5;9m\1\033[0m",
        data,
        flags=re.MULTILINE,
    )
    os.environ["LESS"] = os.environ.get("LESS", "FRX")
    click.echo_via_pager(data)


def die(message: str) -> None:
    """Send a notification with the given message and exit."""
    icon = "dialog-warning"
    call(["notify-send", "-i", icon, "passata", message])
    sys.exit(1)


def lock_file(path: str | Path) -> TextIO:
    """Open and lock a temporary file associated with `path`.

    The file will be deleted when the program exits.

    By locking the database, we can assure that only one passata
    process that is executing a database modifying command, can be
    running at a time. Read-only commands should not acquire the lock.
    """
    # Don't lock the file itself because the lock would get lost on
    # write, and if we're editing, it could be written multiple times.
    lockpath = f"{path}.lock"

    # Open with 'a' (i.e. append) to prevent truncation
    lock = open(lockpath, "a", encoding="utf-8")
    try:
        fcntl.lockf(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
    except IOError:
        sys.exit("Another passata process is editing the database")

    atexit.register(unlock_file, path)

    # Register the lock file's file descriptor to prevent it from closing.
    # If there is no current context the caller is responsible to keep the lock
    # alive as long as needed.
    try:
        click.get_current_context().obj["_lock"] = lock
    except RuntimeError:
        pass

    return lock


def unlock_file(path: str | Path) -> None:
    """Remove the lock file, which also releases the lock."""
    lockpath = f"{path}.lock"
    try:
        os.unlink(lockpath)
    except FileNotFoundError:
        pass


def schedule_clear_clipboard(timeout: int) -> None:
    """Clear clipboard after timeout seconds.

    Write a bash script in /tmp/ and execute it on the background.
    """
    scriptpath = "/tmp/clear-clipboard.sh"

    with open(scriptpath, "w") as f:
        f.writelines(
            [
                "#!/bin/bash\n",
                "\n",
                f"sleep {timeout}\n",
                "echo -n '' | pbcopy\n",
            ]
        )

    os.chmod(scriptpath, 0o755)

    subprocess.Popen(scriptpath, stdout=subprocess.PIPE, stderr=subprocess.PIPE)


def to_clipboard(data: str, timeout: int) -> None:
    """Put `data` to clipboard until `timeout` seconds pass.

    If `timeout` is 0, the clipboard is not cleared.
    """
    command = (
        ["pbcopy", "w"]
        if sys.platform == "darwin"
        else ["xsel", "-i", "-b", "-t", str(timeout * 1000)]
    )
    call(command, input=data)

    if sys.platform == "darwin" and timeout > 0:
        schedule_clear_clipboard(timeout)


def confirm(message: str, force: bool) -> None:
    """Exit if the user does not agree."""
    if not force and not click.confirm(message):
        sys.exit(0)


def confirm_overwrite(filename: str | Path, force: bool) -> None:
    """Exit if the file exists and the user wants it."""
    if os.path.isfile(filename):
        confirm(f"Overwrite {filename}?", force)


def isgroup(name: str) -> bool:
    """Return whether `name` is in 'groupname' or 'groupname/' format."""
    return "/" not in name or not name.split("/")[1]


def split(name: str | None) -> tuple[str | None, str | None]:
    """Split `name` to group name and entry name."""
    if not name:
        groupname, entryname = None, None
    elif isgroup(name):
        groupname, entryname = name.rstrip("/"), None
    else:
        try:
            groupname, entryname = name.split("/")
        except ValueError:
            sys.exit(f"{name} is nested too deeply")

    return groupname, entryname


def to_dict(data: str | None) -> dict:
    """Turn yaml string to dict."""
    # Return empty dict for empty string or None
    if not data:
        return {}

    return yaml.safe_load(data)


def to_string(data: dict | None) -> str:
    """Turn dict to yaml string."""
    # Return empty string for empty dict or None
    if not data:
        return ""

    return yaml.safe_dump(
        data,
        default_flow_style=False,
        allow_unicode=True,
        sort_keys=False,
    )


# Config
def read_config(confpath: Path) -> Config:
    """Read the configuration file and return it as a dict."""
    try:
        return to_dict(confpath.read_text())
    except FileNotFoundError:
        sys.exit("Run `passata init` first")


def write_config(confpath: Path, config: Config, force: bool) -> None:
    """Write the configuration file."""
    confirm_overwrite(confpath, force)
    confpath.parent.mkdir(parents=True, exist_ok=True)
    confpath.write_text(to_string(config))


def default_gpg_id() -> str:
    """Return the id of the first gpg secret key."""
    command = ["gpg", "--list-secret-keys"]
    gpg_ids = re.search(r"<(.*)>", out(command))
    if gpg_ids is None:
        sys.exit("No gpg secret keys found")
    return gpg_ids.group(1)


# Database
class DB:
    """A passata database."""

    def __init__(
        self,
        path: str | None,
        pre_read_hook: Path | None = None,
        post_write_hook: Path | None = None,
    ):
        self.db: Database = {}
        self.data: str | None = None
        self.path: str | None = path
        self.pre_read_hook: Path | None = pre_read_hook
        self.post_write_hook: Path | None = post_write_hook
        self.registered_post_write_hook: bool = False

    def __iter__(self) -> Iterator[tuple[str, str]]:
        for groupname in self.db:
            for entryname in self.db[groupname]:
                yield groupname, entryname

    def groups(self) -> Iterator[str]:
        """Iterate in group names."""
        yield from self.db

    @staticmethod
    def decrypt(path: str) -> str:  # pragma: no cover
        """Decrypt the contents of the given file using gpg."""
        return out(["gpg", "-d", path])

    def read(self, lock: bool = False) -> None:
        """Return the database as a plaintext string."""
        self.execute_pre_read_hook()
        assert self.path is not None
        if not os.path.isfile(self.path):
            sys.exit(f"Database file ({self.path}) does not exist")
        if lock:
            lock_file(self.path)
        self.data = self.decrypt(self.path)
        self.db = to_dict(self.data)
        self.validate()

    @staticmethod
    def encrypt(data: str, gpg_id: str) -> str:  # pragma: no cover
        """Encrypt given text using gpg."""
        return out(["gpg", "-ear", gpg_id], input=data)

    def write(self, gpg_id: str, force: bool = True) -> None:
        """Write the database as an encrypted string."""
        assert self.path is not None
        confirm_overwrite(self.path, force)
        data = to_string(self.db)
        if data == self.data:
            return
        encrypted = self.encrypt(data, gpg_id)
        # Write to a temporary file, make sure the data has reached the
        # disk and replace the database with the temporary file using
        # os.replace() which is guaranteed to be an atomic operation.
        with tempfile.NamedTemporaryFile(
            mode="w", dir=os.path.dirname(self.path), delete=False
        ) as temp:
            temp.write(encrypted)
            temp.flush()
            os.fsync(temp.fileno())
        os.replace(temp.name, self.path)
        self.data = data
        if not self.registered_post_write_hook:
            atexit.register(self.execute_post_write_hook)
            self.registered_post_write_hook = True

    def get(self, name: str | None) -> dict[str, Any] | None:
        """Return database, group or entry."""
        groupname, entryname = split(name)

        # Get the whole database
        if not groupname:
            return self.db

        # Get a whole group
        if not entryname:
            return self.db.get(groupname)

        # Entry should exist
        if groupname not in self.db:
            return None

        # Get a single entry
        return self.db[groupname].get(entryname)

    def put(self, name: str | None, subdict: dict | None) -> None:
        """Add or replace subdict creating group if needed."""
        # Remove if given empty dict
        if not subdict:
            self.pop(name)
            return

        groupname, entryname = split(name)

        # Put the whole database
        if not groupname:
            self.db = subdict
            self.sort()

        # Put a whole group
        elif not entryname:
            self.db[groupname] = subdict
            self.sort_group(groupname)

        # Put a single entry
        else:
            if groupname not in self.db:
                self.db[groupname] = {}
            self.db[groupname][entryname] = subdict
            self.sort_group(groupname)

    def pop(self, name: str | None, force: bool = False) -> dict | None:
        """Remove subdict and every empty parent and return it."""
        groupname, entryname = split(name)

        # Remove the whole database
        if not groupname:
            confirm("Delete the whole database?", force)
            self.db.clear()
            # Maybe we should copy and return the original db
            # for consistency but it's not needed anywhere.
            return None

        # Group should exist
        if groupname not in self.db:
            return None

        # Remove a whole group
        if not entryname:
            confirm(f"Delete group '{groupname}'?", force)
            return self.db.pop(groupname)

        # Entry should exist
        if entryname not in self.db[groupname]:
            return None

        # Remove a single entry
        confirm(f"Delete '{name}'?", force)
        entry = self.db[groupname].pop(entryname)
        if not self.db[groupname]:
            del self.db[groupname]
        return entry

    def ls(self, groupname: str | None = None, no_tree: bool = False) -> None:
        """List entries in a tree-like format."""
        lines = []
        if groupname:
            groupname = groupname.rstrip("/")
            if groupname not in self.groups():
                sys.exit(f"{groupname} not found")
            group = self.get(groupname)
            assert group is not None
            for entryname in group:
                lines.append(entryname)
        elif no_tree:
            for groupname, entryname in self:
                lines.append(f"{groupname}/{entryname}")
        else:
            for groupname in self.groups():
                lines.append(click.style(groupname, fg="blue", bold=True))
                group = self.get(groupname)
                assert group is not None
                entrynames = list(group)
                for entryname in entrynames[:-1]:
                    lines.append(f"├── {entryname}")
                lines.append(f"└── {entrynames[-1]}")
        if lines:
            echo("\n".join(lines))

    def find(self, names: Sequence[str]) -> DB:
        names = [name.lower() for name in names]
        matches = DB(path=None)
        for groupname, entryname in self:
            name = f"{groupname}/{entryname}"
            if any(name in entryname.lower() for name in names):
                matches.put(name, self.get(name))
                continue
            for keyword in self.keywords(name):
                if any(name in keyword for name in names):
                    matches.put(f"{name} ({keyword})", self.get(name))
                    break

        return matches

    def keywords(self, name: str) -> list[str]:
        """Return the entry's keywords field as a list of strings."""
        entry = self.get(name)
        assert entry is not None
        keywords = entry.get("keywords")
        if isinstance(keywords, list):
            return [str(keyword).lower() for keyword in keywords]
        if keywords is not None:
            return [str(keywords).lower()]
        return []

    def sort_group(self, groupname: str) -> None:
        """Sort entries in the given group."""
        group = self.db[groupname]
        self.db[groupname] = dict(sorted(group.items(), key=lambda t: t[0]))

    def sort(self) -> None:
        """Sort entries in each group of the database."""
        for groupname in self.db:
            self.sort_group(groupname)

    def execute_pre_read_hook(self) -> None:
        """Execute pre-read hook if existing."""
        if self.pre_read_hook is not None:
            call(self.pre_read_hook)

    def execute_post_write_hook(self) -> None:
        """Execute post-write hook if existing."""
        if self.post_write_hook is not None:
            call(self.post_write_hook)

    def validate(self) -> None:
        """Validate the database.

        Exit if the database is not a valid Database.
        """
        if not isinstance(self.db, dict):
            sys.exit("Database is not a dict")

        for groupname, group in self.db.items():
            if not isinstance(group, dict):
                sys.exit(f"Group '{groupname}' is not a dict")

            for entryname, entry in group.items():
                if not isinstance(entry, dict):
                    sys.exit(f"Entry '{entryname}' is not a dict")


# Commands
@click.group(
    context_settings={
        "help_option_names": ["-h", "--help"],
        "max_content_width": 100,
    }
)
@click.option(
    "--config",
    type=click.Path(dir_okay=False),
    default=os.path.join(click.get_app_dir("passata", force_posix=True), "config.yml"),
    envvar="PASSATA_CONFIG_PATH",
    help="Path of the configuration file.",
)
@click.option("--color/--no-color", default=None, help="Colorize the output.")
@click.version_option(version=__version__)
@click.pass_context
def cli(ctx: click.Context, config: str, color: bool | None) -> None:
    """A simple password manager, inspired by pass."""
    confpath = Path(config).expanduser()
    obj: Obj = {"_confpath": confpath}
    ctx.obj = obj
    command = ctx.invoked_subcommand
    assert command is not None
    # When init is invoked there isn't supposed to be a config file yet
    if command != "init":
        config_data = read_config(confpath)
        cmd_config = config_data.get(command, {})
        if not isinstance(cmd_config, dict):
            sys.exit(f"Invalid configuration for command {command}")

        cmd_config.update(
            {
                key: value
                for key, value in config_data.items()
                if not isinstance(value, dict) and key not in cmd_config
            }
        )
        ctx.color = color if color is not None else config_data.get("color")
        confdir = confpath.parent

        path = confdir / "hooks" / "pre-read"
        pre_read_hook = path if path.is_file() else None
        path = confdir / "hooks" / "post-write"
        post_write_hook = path if path.is_file() else None

        dbpath = config_data["database"]
        if not isinstance(dbpath, str):
            sys.exit(f"Value for database ({dbpath}) is not a valid string")

        db = DB(
            path=os.path.expanduser(dbpath),
            pre_read_hook=pre_read_hook,
            post_write_hook=post_write_hook,
        )

        # We put the config in obj for the options that
        # don't correspond to a command-line option.
        ctx.obj.update(config_data)
        ctx.obj["_db"] = db
        ctx.default_map = {command: cmd_config}


@cli.command()
@click.option("-f", "--force", is_flag=True, help="Do not prompt for confirmation.")
@click.option(
    "-g",
    "--gpg-id",
    prompt="GnuPG ID",
    default=default_gpg_id,
    help="GnuPG ID for database encryption.",
)
@click.option(
    "-p",
    "--path",
    prompt="Database path",
    default="~/.passata.gpg",
    type=click.Path(dir_okay=False),
    help="Database path.",
)
@click.pass_obj
def init(obj: Obj, force: bool, gpg_id: str, path: str) -> None:
    """Initialize password database."""
    dbpath = os.path.abspath(os.path.expanduser(path))
    lock_file(dbpath)
    confpath = obj["_confpath"]
    config = {"database": dbpath, "gpg_id": gpg_id}
    write_config(confpath, config, force)
    obj.update(config)
    db = DB(dbpath)
    db.write(gpg_id, force)


@cli.command("config")
@click.option(
    "-e",
    "--editor",
    default=os.environ.get("EDITOR", "vim"),
    help="Which editor to use.",
)
@click.pass_obj
def config_(obj: Obj, editor: str) -> None:
    """Edit the configuration file."""
    click.edit(filename=obj["_confpath"], editor=editor)


@cli.command()
@click.option(
    "-n",
    "--no-tree",
    is_flag=True,
    help="Print entries in 'groupname/entryname' format.",
)
@click.argument("group", required=False)
@click.pass_obj
def ls(obj: Obj, group: str | None, no_tree: bool) -> None:
    """List entries in a tree-like format."""
    db: DB = obj["_db"]
    db.read()
    db.ls(group, no_tree)


@cli.command()
@click.option(
    "-n",
    "--no-tree",
    is_flag=True,
    help="Print entries in 'groupname/entryname' format.",
)
@click.option("-p", "--print", "print_", is_flag=True, help="Show the found entries.")
@click.option(
    "-c/-C",
    "--clip/--no-clip",
    default=False,
    help="Copy the first result's password to clipboard.",
)
@click.option(
    "-t",
    "--timeout",
    default=45,
    help="Number of seconds until the clipboard is cleared.",
)
@click.argument("names", nargs=-1)
@click.pass_obj
def find(
    obj: Obj,
    names: list[str],
    no_tree: bool,
    print_: bool,
    clip: bool,
    timeout: int,
) -> None:
    """List matching entries in a tree-like format."""
    db: DB = obj["_db"]
    db.read()
    matches = db.find(names)

    if print_:
        echo(to_string(matches.db).strip())
    else:
        matches.ls(no_tree=no_tree)

    if matches.db and clip:
        groupname, entryname = next(iter(matches))
        first_match = matches.get(f"{groupname}/{entryname}")
        assert first_match is not None
        to_clipboard(first_match["password"], timeout)
        click.echo()
        click.echo(f"Copied password of {groupname}/{entryname} to clipboard.")


@cli.command(short_help="Show entry, group or the whole database.")
@click.option(
    "-c/-C",
    "--clip/--no-clip",
    default=False,
    help="Whether to copy password to clipboard or print.",
)
@click.option(
    "-t",
    "--timeout",
    default=45,
    help="Number of seconds until the clipboard is cleared.",
)
@click.argument("name", required=False)
@click.pass_obj
def show(obj: Obj, name: str | None, clip: bool, timeout: int) -> None:
    """Decrypt and print the contents of NAME.

    NAME can be an entry, a group, or omitted to print the whole database. If
    NAME is an entry and --clip is specified, the password will stay in the
    clipboard for `timeout` seconds.
    """
    db: DB = obj["_db"]
    db.read()
    entry = db.get(name)
    if entry is None:
        sys.exit(f"{name} not found")

    if clip:
        if name is None:
            sys.exit("Can't put the entire database to clipboard")
        if isgroup(name):
            sys.exit("Can't put the entire group to clipboard")
        to_clipboard(entry["password"], timeout=timeout)
    else:
        echo(to_string(entry).strip())


def do_insert(obj: Obj, name: str, password: str, force: bool) -> str | None:
    """Insert `password` into `name` without deleting everything else.

    If `name` is already in the database, keep a backup of the old password.
    Return the old password or None if there wasn't one.
    """
    if isgroup(name):
        sys.exit(f"{name} is a group")
    db: DB = obj["_db"]
    db.read(lock=True)
    entry = db.get(name)
    old_password = None
    if entry is None:
        db.put(name, {"password": password})
    else:
        if "password" in entry:
            confirm(f"Overwrite {name}?", force)
            old_password = entry["password"]
            entry["old_password"] = old_password
        entry["password"] = password

    db.write(obj["gpg_id"])
    return old_password


@cli.command()
@click.argument("name")
@click.option("-f", "--force", is_flag=True, help="Do not prompt for confirmation.")
@click.password_option(help="Give password instead of being prompted for it.")
@click.pass_obj
def insert(obj: Obj, name: str, force: bool, password: str) -> None:
    """Insert a new password.

    When overwriting an existing entry, the old password is kept in
    <old_password>.
    """
    do_insert(obj, name, password, force)


def get_wordpath(wordpath: str | None) -> str:
    """Return the path of the diceware words file."""
    if wordpath is not None:
        return wordpath

    filename = "eff_large_wordlist.txt"
    directories = ["/usr/local/share/passata", "/usr/share/passata"]
    for directory in directories:
        wordpath = os.path.join(directory, filename)
        if os.path.exists(wordpath):
            return wordpath

    sys.exit("--words option requires a wordpath")


def generate_password(
    length: int | None,
    entropy: float | None,
    symbols: bool,
    words: bool,
    wordpath: str | None,
    force: bool,
) -> str:
    """Generate a random password."""
    choice = random.SystemRandom().choice
    pool: Sequence
    if words:
        wordpath = get_wordpath(wordpath)
        try:
            with open(os.path.expanduser(wordpath), encoding="utf-8") as f:
                pool = f.read().strip().split("\n")
        except FileNotFoundError:
            sys.exit(f"{wordpath}: No such file or directory")
    else:
        chargroups = [string.ascii_letters, string.digits]
        if symbols:
            chargroups.append(string.punctuation)
        pool = "".join(chargroups)

    if entropy is not None:
        length = math.ceil(entropy / math.log2(len(pool)))
    else:
        assert length is not None
        entropy = length * math.log2(len(pool))

    if entropy < 32:
        msg = f"Generate password with only {entropy:.3f} bits of entropy?"
        confirm(msg, force)

    sep = " " if words else ""
    password = sep.join(choice(pool) for _ in range(length))
    click.echo(f"Generated password with {entropy:.3f} bits of entropy")
    return password


@cli.command()
@click.argument("name", required=False)
@click.option("-f", "--force", is_flag=True, help="Do not prompt for confirmation.")
@click.option("-p/-P", "--print/--no-print", "print_", help="Print the password.")
@click.option(
    "-c/-C", "--clip/--no-clip", default=True, help="Copy password to clipboard."
)
@click.option(
    "-t",
    "--timeout",
    default=45,
    help="Number of seconds until the clipboard is cleared.",
)
@click.option(
    "-l",
    "--length",
    type=click.IntRange(1),
    metavar="INTEGER",
    default=20,
    help="Length of the generated password.",
)
@click.option(
    "-e",
    "--entropy",
    type=click.FLOAT,
    help="Calculate length for given bits of entropy (takes precedence over --length).",
)
@click.option(
    "-s/-S",
    "--symbols/--no-symbols",
    default=True,
    help="Use symbols in the generated password.",
)
@click.option(
    "-w/-W",
    "--words/--no-words",
    is_flag=True,
    help="Generate diceware-like passphrase.",
)
@click.option(
    "--wordpath",
    type=click.Path(dir_okay=False),
    help="List of words for passphrase generation.",
)
@click.pass_context
def generate(
    ctx: click.Context,
    name: str | None,
    force: bool,
    print_: bool,
    clip: bool,
    timeout: int,
    length: int | None,
    entropy: float | None,
    symbols: bool,
    words: bool,
    wordpath: str,
) -> None:
    """Generate a random password.

    When overwriting an existing entry, the old password is kept in
    <old_password>.
    """
    obj: Obj = ctx.obj

    # Entropy takes precedence over length but cli params take precedence over
    # config.
    # TODO: Add test
    entropy_source = ctx.get_parameter_source("entropy")
    length_source = ctx.get_parameter_source("length")
    if entropy_source is not None and length_source is not None:
        if entropy_source.name == "DEFAULT_MAP" and length_source.name == "COMMANDLINE":
            entropy = None

    password = generate_password(length, entropy, symbols, words, wordpath, force)

    if print_ or (not name and not clip):
        click.echo(password)

    old_password = do_insert(obj, name, password, force) if name else None

    if not clip:
        return

    if old_password is not None:
        to_clipboard(old_password, timeout=0)
        click.echo("Copied old password to clipboard.")
        click.pause()

    to_clipboard(password, timeout=timeout)
    click.echo("Copied generated password to clipboard.")


@cli.command()
@click.argument("name", required=False)
@click.option(
    "-e",
    "--editor",
    default=os.environ.get("EDITOR", "vim"),
    help="Which editor to use.",
)
@click.pass_obj
def edit(obj: Obj, name: str, editor: str) -> None:
    """Edit entry, group or the whole database."""

    class EventHandler(watchdog.events.PatternMatchingEventHandler):
        """Write database when temp file is modified."""

        def __init__(self, path: str) -> None:
            self.path = path
            super().__init__(
                patterns=["*.yml"],
                ignore_directories=True,
                case_sensitive=False,
            )

        def on_modified(self, event: watchdog.events.FileSystemEvent) -> None:
            if self.path not in event.src_path:
                return

            with open(event.src_path, encoding="utf-8") as f:
                updated = f.read()

            # If the file is empty or contains invalid yaml,
            # ignore it. Once the editor exits, we will
            # read it one last time and handle it properly.
            try:
                data = to_dict(updated)
            except yaml.scanner.ScannerError:
                return
            if not data:
                return
            db.put(name, data)
            db.write(obj["gpg_id"])

    db: DB = obj["_db"]
    db.read(lock=True)
    subdict = db.get(name) or {}
    original = to_string(subdict)
    # Describe what is being edited in a comment at the top
    comment = name or "passata database"
    text = f"# {comment}\n{original}"

    temp = tempfile.NamedTemporaryFile(mode="w+", prefix="passata-", suffix=".yml")
    temp.write(text)
    temp.flush()

    path = os.path.dirname(temp.name)
    event_handler = EventHandler(temp.name)
    observer = watchdog.observers.Observer()
    observer.schedule(event_handler, path=path, recursive=True)
    observer.start()

    click.edit(filename=temp.name, editor=editor)

    observer.stop()
    observer.join()

    # Read the file one last time. It may have already been read
    # in the handler, but it's not guaranteed. If for example the
    # user saved and exited the editor, there is a race condition.
    with open(temp.name, encoding="utf-8") as f:
        updated = f.read()

    temp.close()

    try:
        data = to_dict(updated)
    except yaml.scanner.ScannerError:
        sys.exit("Invalid yaml")
    else:
        db.put(name, data)
        db.write(obj["gpg_id"])


@cli.command()
@click.argument("names", nargs=-1, required=True, metavar="ENTRY/GROUP...")
@click.option("-f", "--force", is_flag=True, help="Do not prompt for confirmation.")
@click.pass_obj
def rm(obj: Obj, names: list[str], force: bool) -> None:
    """Remove entries or groups."""
    db: DB = obj["_db"]
    db.read(lock=True)
    if len(names) == 1:
        if db.pop(names[0], force) is None:
            sys.exit(f"{names[0]} not found")
        db.write(obj["gpg_id"])
        return

    confirm(f"Delete {len(names)} arguments?", force)

    for name in names:
        if db.pop(name, force=True) is None:
            sys.exit(f"{name} not found")

    db.write(obj["gpg_id"])


@cli.command(short_help="Move or rename entries.")
@click.argument("source", nargs=-1, required=True)
@click.argument("dest", metavar="DEST/GROUP")
@click.option("-f", "--force", is_flag=True, help="Do not prompt for confirmation.")
@click.pass_obj
def mv(obj: Obj, source: str, dest: str, force: bool) -> None:
    """Rename SOURCE to DEST or move SOURCE(s) to GROUP."""
    db: DB = obj["_db"]
    db.read(lock=True)
    if len(source) > 1 and not isgroup(dest):
        sys.exit(f"{dest} is not a group")

    if len(source) == 1 and isgroup(source[0]):
        if not isgroup(dest):
            sys.exit(f"{dest} is not a group")
        groupname = source[0]
        if db.get(groupname) is None:
            sys.exit(f"{groupname} not found")
        if db.get(dest) is not None:
            # Do not implicitly remove a whole group even by asking the
            # user. Instead we could prompt for merging the two groups.
            sys.exit(f"{dest} already exists")
        group = db.pop(groupname, force=True)
        db.put(dest, group)
    else:
        for name in source:
            if db.get(name) is None:
                sys.exit(f"{name} not found")
            _, entryname = split(name)
            assert entryname is not None
            # os.path.join() because using '/'.join('groupname/', 'entryname')
            # would result in two slashes.
            newname = os.path.join(dest, entryname) if isgroup(dest) else dest
            if db.get(newname) is not None:
                confirm(f"Overwrite {newname}?", force)
            entry = db.pop(name, force=True)
            db.put(newname, entry)

    db.write(obj["gpg_id"])


# Autotype
def active_window() -> tuple[str, str]:  # pragma: no cover
    """Get active window id and name."""
    window_id = out(["xdotool", "getactivewindow"])
    window_name = out(["xdotool", "getwindowname", window_id])
    return window_id, window_name


def keyboard(key: str, entry: Entry, delay: str) -> None:
    """Simulate keyboard input for `key` using xdotool."""
    if key[0] == "<" and key[-1] == ">":
        value = entry.get(key[1:-1])
        if not value:
            die(f"{key[1:-1]} not found")
        # `value` could be an int so we explicitly convert it to str
        call(["xdotool", "type", "--clearmodifiers", "--delay", delay, str(value)])
    elif key[0] == "!":
        duration = float(key[1:])
        time.sleep(duration)
    else:
        call(["xdotool", "key", key])


def get_autotype_keys(entry: Entry) -> list[str]:
    """Return a list with the items that need to be typed."""
    data: str | None = entry.get("autotype")

    if data is None:
        if entry.get("username") and entry.get("password"):
            data = "<username> Tab <password> Return"
        elif entry.get("password"):
            data = "<password> Return"
        else:
            die("Don't know what to type :(")

    assert isinstance(data, str)

    return data.split()


@cli.command()
@click.option("-s", "--sequence", help="Autotype sequence.")
@click.option("-d", "--delay", default="50", help="Delay between keystrokes in ms.")
@click.option("-m", "--menu", default="dmenu", help="dmenu provider command.")
@click.pass_obj
def autotype(obj: Obj, sequence: str, delay: str, menu: str) -> None:
    """Type login credentials."""
    db: DB = obj["_db"]
    db.read()
    window = active_window()

    # Put the entries that match the window title in `matches`, and every entry
    # in `names`, to fall back to that if there are no matches.
    names = []
    matches = []
    for groupname, entryname in db:
        name = f"{groupname}/{entryname}"
        names.append(name)
        keywords = [entryname.lower()] + db.keywords(name)
        title = window[1].lower()
        if any(keyword in title for keyword in keywords):
            matches.append(name)

    if len(matches) == 1:
        choice = matches[0].strip()
    else:
        command = shlex.split(menu) if isinstance(menu, str) else menu
        choices = "\n".join(sorted(matches if matches else names))
        choice = out(command, input=choices).strip()

    entry = db.get(choice)
    assert entry is not None
    keys = sequence.split() if sequence else get_autotype_keys(entry)
    for key in keys:
        if active_window() != window:  # pragma: no cover
            die("Window has changed")
        keyboard(key, entry, delay)


if __name__ == "__main__":
    cli()  # pylint: disable=no-value-for-parameter
