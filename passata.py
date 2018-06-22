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

import atexit
import collections
import fcntl
import math
import os
import random
import re
import string
import subprocess
import sys
import tempfile
import time

import click
import pyinotify
import yaml

__version__ = '0.1.0'


# Utilities
def call(command, stdout=None, input=None):
    """Run command, optionally passing `input` to stdin.

    By default, standard output is printed and ignored and None is returned.
    Setting stdout=subprocess.PIPE, will capture and return standard output
    instead.
    """
    try:
        return subprocess.run(
            command,
            input=input,
            stdout=stdout,
            stderr=subprocess.DEVNULL,
            check=True,
            universal_newlines=True
        ).stdout
    except subprocess.CalledProcessError as e:
        sys.exit(e)
    except FileNotFoundError:
        sys.exit("Executable '%s' not found" % command[0])


def out(command, input=None):
    """Run command, optionally passing `input` to stdin, and return output.

    The output usually comes back with a trailing newline and it needs to be
    striped if not needed.
    """
    return call(command, stdout=subprocess.PIPE, input=input)


def echo(data, color=False):
    """Print data to stdout or via a pager if it doesn't fit on screen."""
    if color:
        # Bright blue key (color 12) and bright yellow colon (color 11).
        # Colors are applied manually using ANSI escape codes because
        # click.style does not support bright colors. The key ends at the
        # first colon that is followed by either a space or a newline.
        data = re.sub(r'(^\s*.*?):(\s)',
                      r'\033[38;5;12m\1\033[38;5;11m:\033[0m\2',
                      data, flags=re.MULTILINE)
        data = re.sub(r'(^\s*-\s)', r'\033[38;5;9m\1\033[0m',
                      data, flags=re.MULTILINE)
    _, terminal_lines = click.get_terminal_size()
    # Plus one line for the prompt
    if data.count('\n') + 1 >= terminal_lines:  # pragma: no cover
        click.echo_via_pager(data)
    else:
        click.echo(data)


def die(message):
    """Send a notification with the given message and exit."""
    icon = 'dialog-warning'
    call(['notify-send', '-i', icon, 'passata', message])
    sys.exit(1)


def lock_file(path):
    """Open and lock a temporary file associated with `path`.

    The file will be deleted when the program exits.

    By locking the database, we can assure that only one passata
    process that is executing a database modifying command, can be
    running at a time. Read-only commands should not acquire the lock.
    """
    # Don't lock the file itself because the lock would get lost on
    # write, and if we're editing, it could be written multiple times.
    lockpath = '%s.lock' % path

    # Open with 'a' (i.e. append) to prevent truncation
    lock = open(lockpath, 'a')
    try:
        fcntl.lockf(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
    except IOError:
        sys.exit("Another passata process is editing the database")

    atexit.register(unlock_file, path)

    # Register the lock file's file descriptor to prevent it from closing
    click.get_current_context().obj['_lock'] = lock


def unlock_file(path):
    """Remove the lock file, which also releases the lock."""
    lockpath = '%s.lock' % path
    try:
        os.unlink(lockpath)
    except FileNotFoundError:
        pass


def to_clipboard(data, timeout):
    """Put `data` to clipbord until `timeout` seconds pass."""
    command = ['xsel', '-i', '-b', '-t', str(timeout * 1000)]
    call(command, input=data)


def confirm(message, force):
    """Exit if the user does not agree."""
    if not force and not click.confirm(message):
        sys.exit(0)


def confirm_overwrite(filename, force):
    """Exit if the file exists and the user wants it."""
    if os.path.isfile(filename):
        confirm("Overwrite %s?" % filename, force)


def isgroup(name):
    """Return whether `name` is in 'groupname' or 'groupname/' format."""
    return '/' not in name or not name.split('/')[1]


def split(name):
    """Split `name` to group name and entry name."""
    if not name:
        groupname, entryname = None, None
    elif isgroup(name):
        groupname, entryname = name.rstrip('/'), None
    else:
        try:
            groupname, entryname = name.split('/')
        except ValueError:
            sys.exit("%s is nested too deeply" % name)

    return groupname, entryname


def to_dict(data):
    """Turn yaml string to dict."""
    # Return empty dict for empty string or None
    if not data:
        return collections.OrderedDict()

    class OrderedLoader(yaml.SafeLoader):
        """yaml.Loader subclass that safely loads to OrderedDict."""

    def _constructor(loader, node):
        loader.flatten_mapping(node)
        return collections.OrderedDict(loader.construct_pairs(node))

    tag = yaml.resolver.BaseResolver.DEFAULT_MAPPING_TAG
    OrderedLoader.add_constructor(tag, _constructor)
    return yaml.load(data, Loader=OrderedLoader)


def to_string(data):
    """Turn dict to yaml string."""
    # Return empty string for empty dict or None
    if not data:
        return ''

    class OrderedDumper(yaml.SafeDumper):
        """yaml.Dumper subclass that safely dumps from OrderedDict."""

    def _representer(dumper, data):
        tag = yaml.resolver.BaseResolver.DEFAULT_MAPPING_TAG
        return dumper.represent_mapping(tag, data.items())

    OrderedDumper.add_representer(collections.OrderedDict, _representer)
    return yaml.dump(data, Dumper=OrderedDumper,
                     default_flow_style=False, allow_unicode=True)


# Config
def read_config(confpath):
    """Read the configuration file and return it as a dict."""
    config = {
        'editor': os.environ.get('EDITOR', 'vim'),
        'dmenu': ['dmenu'],
        'length': 20,
        'entropy': None,
        'symbols': True,
        'wordlist': None,
        'color': True,
        'timeout': 45,
    }
    try:
        with open(confpath) as f:
            data = f.read()
    except FileNotFoundError:
        sys.exit("Run `passata init` first")

    config.update(to_dict(data))
    return config


def write_config(confpath, config, force):
    """Write the configuration file."""
    template = (
        "# Configuration file for passata\n"
        "# Available options:\n"
        "# database: Path of the database file\n"
        "# gpg_id: GnuPG ID used for database encryption\n"
        "# editor: Editor used for editing database entries "
        "[default: EDITOR or vim]\n"
        "# dmenu: dmenu provider command with optional arguments "
        "[default: ['dmenu']]\n"
        "# length: Default length of generated passwords [default: 20]\n"
        "# entropy: Calculate length for given bits of entropy\n"
        "# symbols: Whether to use symbols in the generated password "
        "[default: true]\n"
        "# wordlist: List of words for passphrase generation\n"
        "# color: Whether to colorize the output [default: true]\n"
        "# timeout: Number of seconds until the clipboard is cleared "
        "[default: 45]\n"
        "%s"
    )
    confirm_overwrite(confpath, force)
    os.makedirs(os.path.dirname(confpath), exist_ok=True)
    with open(confpath, 'w') as f:
        f.write(template % to_string(config))


def option(key):
    """Return the config option for `key`."""
    config = click.get_current_context().obj
    assert key in config
    return config[key]


def default_gpg_id():
    """Return the id of the first gpg secret key."""
    command = ['gpg', '--list-secret-keys']
    gpg_ids = re.search(r'<(.*)>', out(command))
    if gpg_ids is None:
        sys.exit("No gpg secret keys found")
    return gpg_ids.group(1)


# Database
class DB:
    """A passata database."""

    def __init__(self, path=None):
        self.db = collections.OrderedDict()
        self.path = os.path.expanduser(path or option('database'))

    def __iter__(self):
        for groupname in self.db:
            for entryname in self.db[groupname]:
                yield groupname, entryname

    def groups(self):
        """Iterate in group names."""
        yield from self.db

    @staticmethod
    def decrypt(path):  # pragma: no cover
        """Decrypt the contents of the given file using gpg."""
        return out(['gpg', '-d', path])

    def read(self, lock=False):
        """Return the database as a plaintext string."""
        if not os.path.isfile(self.path):
            sys.exit("Database file (%s) does not exist" % self.path)
        if lock:
            lock_file(self.path)
        data = self.decrypt(self.path)
        self.db = to_dict(data)

    @staticmethod
    def encrypt(data, gpg_id=None):  # pragma: no cover
        """Encrypt given text using gpg."""
        gpg_id = gpg_id or option('gpg_id')
        return out(['gpg', '-ear', gpg_id], input=data)

    def write(self, gpg_id=None, force=True):
        """Write the database as an encrypted string."""
        confirm_overwrite(self.path, force)
        data = to_string(self.db)
        encrypted = self.encrypt(data, gpg_id)
        # Write to a temporary file, make sure the data has reached the
        # disk and replace the database with the temporary file using
        # os.replace() which is guaranteed to be an atomic operation.
        fd = tempfile.NamedTemporaryFile(
            mode='w', dir=os.path.dirname(self.path), delete=False)
        fd.write(encrypted)
        fd.flush()
        os.fsync(fd.fileno())
        fd.close()
        os.replace(fd.name, self.path)

    def get(self, name):
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

    def put(self, name, subdict):
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
                self.db[groupname] = collections.OrderedDict()
            self.db[groupname][entryname] = subdict
            self.sort_group(groupname)

    def pop(self, name, force=False):
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
            confirm("Delete group '%s'?" % groupname, force)
            return self.db.pop(groupname)

        # Entry should exist
        if entryname not in self.db[groupname]:
            return None

        # Remove a single entry
        confirm("Delete '%s'?" % name, force)
        entry = self.db[groupname].pop(entryname)
        if not self.db[groupname]:
            del self.db[groupname]
        return entry

    def list(self, group=None, no_tree=False, color=True):
        """List entries in a tree-like format."""
        lines = []
        if group:
            groupname = group.rstrip('/')
            if groupname not in self.groups():
                sys.exit("%s not found" % groupname)
            for entryname in self.get(groupname):
                lines.append(entryname)
        elif no_tree:
            for groupname, entryname in self:
                lines.append('%s/%s' % (groupname, entryname))
        else:
            for groupname in self.groups():
                lines.append(click.style(groupname, fg='blue', bold=True)
                             if color else groupname)
                entrynames = list(self.get(groupname))
                for entryname in entrynames[:-1]:
                    lines.append("├── %s" % entryname)
                lines.append("└── %s" % entrynames[-1])
        if lines:
            echo('\n'.join(lines))

    def keywords(self, name):
        """Return the entry's keywords field as a list of strings."""
        entry = self.get(name)
        assert entry is not None
        keywords = entry.get('keywords')
        if isinstance(keywords, list):
            return [str(keyword).lower() for keyword in keywords]
        elif keywords is not None:
            return [str(keywords).lower()]
        return []

    def sort_group(self, groupname):
        """Sort entries in the given group."""
        group = self.db[groupname]
        self.db[groupname] = collections.OrderedDict(
            sorted(group.items(), key=lambda t: t[0])
        )

    def sort(self):
        """Sort entries in each group of the database."""
        for groupname in self.db:
            self.sort_group(groupname)


# Commands
@click.group(context_settings={'help_option_names': ['-h', '--help']})
@click.option('--config', type=click.Path(dir_okay=False),
              default=os.path.join(click.get_app_dir('passata'), 'config.yml'),
              envvar='PASSATA_CONFIG_PATH',
              help="Path of the configuration file.")
@click.version_option(version=__version__)
@click.pass_context
def cli(ctx, config):  # noqa: D401
    """A simple password manager, inspired by pass."""
    ctx.obj = {'_confpath': os.path.abspath(os.path.expanduser(config))}
    # When init is invoked there isn't supposed to be a config file yet
    if ctx.invoked_subcommand != 'init':
        ctx.obj.update(read_config(config))


@cli.command()
@click.option('-f', '--force', is_flag=True,
              help="Do not prompt for confirmation.")
@click.option('-g', '--gpg-id', prompt="GnuPG ID", default=default_gpg_id,
              help="GnuPG ID for database encryption.")
@click.option('-p', '--path', prompt="Database path", default='~/.passata.gpg',
              type=click.Path(dir_okay=False), help="Database path.")
@click.pass_obj
def init(obj, force, gpg_id, path):
    """Initialize password database."""
    dbpath = os.path.abspath(os.path.expanduser(path))
    lock_file(dbpath)
    confpath = obj['_confpath']
    config = {'database': dbpath, 'gpg_id': gpg_id}
    write_config(confpath, config, force)
    obj.update(config)
    db = DB()
    db.write(gpg_id, force)


@cli.command()
@click.option('-n', '--no-tree', is_flag=True,
              help="Print entries in 'groupname/entryname' format.")
@click.option('--color/--no-color', is_flag=True,
              default=lambda: option('color'),
              help="Whether to colorize the output.")
@click.argument('group', required=False)
def ls(group, no_tree, color):
    """List entries in a tree-like format."""
    db = DB()
    db.read()
    db.list(group, no_tree, color)


@cli.command()
@click.option('-n', '--no-tree', is_flag=True,
              help="Print entries in 'groupname/entryname' format.")
@click.option('--color/--no-color', is_flag=True,
              default=lambda: option('color'),
              help="Whether to colorize the output.")
@click.option('-s', '--show', 'show_', is_flag=True, default=False,
              help="Whether to show the found entries.")
@click.argument('names', nargs=-1)
def find(names, no_tree, color, show_):
    """List matching entries in a tree-like format."""
    db = DB()
    db.read()
    names = [name.lower() for name in names]
    matches = DB()
    for groupname, entryname in db:
        name = '%s/%s' % (groupname, entryname)
        if any(name in entryname.lower() for name in names):
            matches.put(name, db.get(name))
            continue
        for keyword in db.keywords(name):
            if any(name in keyword for name in names):
                matches.put('%s (%s)' % (name, keyword), db.get(name))
                break
    if show_:
        echo(to_string(matches.db).strip(), color)
    else:
        matches.list(no_tree=no_tree, color=color)


@cli.command(short_help="Show entry, group or the whole database.")
@click.option('-c', '--clip', is_flag=True,
              help="Copy password to clipboard instead of printing.")
@click.option('--color/--no-color', is_flag=True,
              default=lambda: option('color'),
              help="Whether to colorize the output.")
@click.argument('name', required=False)
def show(name, clip, color):
    """Decrypt and print the contents of NAME.

    NAME can be an entry, a group, or omitted to print the whole database. If
    NAME is an entry and --clip is specified, the password will stay in the
    clipboard until it is pasted.
    """
    db = DB()
    db.read()
    entry = db.get(name)
    if entry is None:
        sys.exit("%s not found" % name)

    if clip:
        if name is None:
            sys.exit("Can't put the entire database to clipboard")
        if isgroup(name):
            sys.exit("Can't put the entire group to clipboard")
        to_clipboard(entry['password'], timeout=option('timeout'))
    else:
        echo(to_string(entry).strip(), color)


def do_insert(name, password, force):
    """Insert `password` into `name` without deleting everything else.

    If `name` is already in the database, keep a backup of the old password.
    Return the old password or None if there wasn't one.
    """
    if isgroup(name):
        sys.exit("%s is a group" % name)
    db = DB()
    db.read(lock=True)
    entry = db.get(name)
    old_password = None
    if entry is None:
        db.put(name, {'password': password})
    else:
        if 'password' in entry:
            confirm("Overwrite %s?" % name, force)
            old_password = entry['password']
            entry['old_password'] = old_password
        entry['password'] = password

    db.write()
    return old_password


@cli.command()
@click.argument('name')
@click.option('-f', '--force', is_flag=True,
              help="Do not prompt for confirmation.")
@click.password_option(help="Give password instead of being prompted for it.")
def insert(name, force, password):
    """Insert a new password.

    When overwriting an existing entry, the old password is kept in
    <old_password>.
    """
    do_insert(name, password, force)


def generate_password(length, entropy, symbols, wordlist, force):
    """Generate a random password."""
    choice = random.SystemRandom().choice
    if wordlist:
        try:
            with open(wordlist) as f:
                pool = f.read().strip().split('\n')
        except FileNotFoundError:
            sys.exit("%s: No such file or directory" % wordlist)
    else:
        chargroups = [string.ascii_letters, string.digits]
        if symbols:
            chargroups.append(string.punctuation)
        pool = ''.join(chargroups)
    if entropy is not None:
        length = math.ceil(entropy / math.log2(len(pool)))
    entropy = math.log2(len(pool) ** length)
    if entropy < 32:
        msg = "Generate password with only %.3f bits of entropy?" % entropy
        confirm(msg, force)
    sep = ' ' if wordlist else ''
    password = sep.join(choice(pool) for i in range(length))
    click.echo("Generated password with %.3f bits of entropy" % entropy)
    return password


@cli.command()
@click.argument('name', required=False)
@click.option('-f', '--force', is_flag=True,
              help="Do not prompt for confirmation.")
@click.option('-c', '--clip', is_flag=True,
              help="Copy password to clipboard instead of printing.")
@click.option('-l', '--length', type=click.IntRange(1), metavar='INTEGER',
              default=lambda: option('length'),
              help="Length of the generated password.")
@click.option('-e', '--entropy', type=click.IntRange(1), metavar='INTEGER',
              default=lambda: option('entropy'),
              help="Calculate length for given bits of entropy.")
@click.option('--symbols/--no-symbols', is_flag=True,
              default=lambda: option('symbols'),
              help="Whether to use symbols in the generated password.")
@click.option('-w', '--wordlist', type=click.Path(dir_okay=False),
              help=("List of words for passphrase generation."))
def generate(name, force, clip, length, entropy, symbols, wordlist):
    """Generate a random password.

    When overwriting an existing entry, the old password is kept in
    <old_password>.
    """
    password = generate_password(length, entropy, symbols, wordlist, force)
    old_password = do_insert(name, password, force) if name else None
    if clip:
        if old_password is not None:
            to_clipboard(old_password, timeout=0)
            click.echo("Put old password to clipboard.")
            click.pause()
        timeout = option('timeout')
        to_clipboard(password, timeout=timeout)
        click.echo("Put generated password to clipboard. "
                   "Will clear after %s seconds." % timeout)
    else:
        click.echo(password)


@cli.command()
@click.argument('name', required=False)
def edit(name):
    """Edit entry, group or the whole database."""
    db = DB(option('database'))
    db.read(lock=True)
    subdict = db.get(name) or collections.OrderedDict()
    original = to_string(subdict)
    # Describe what is being edited in a comment at the top
    comment = name or "passata database"
    text = "# %s\n%s" % (comment, original)

    fp = tempfile.NamedTemporaryFile(
        mode='w+', prefix='passata-', suffix='.yml'
    )
    fp.write(text)
    fp.flush()

    class EventHandler(pyinotify.ProcessEvent):
        """Custom pyinotify event handler."""

        @staticmethod
        def process_IN_MODIFY(event):  # pylint: disable=invalid-name
            """Update the database each time the temporary file is saved."""
            if event.pathname != fp.name:
                return
            with open(fp.name) as f:
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
            db.write(gpg_id)

    # click does not preserve the context in-between threads, so
    # we pass gpg_id into the closure as a nonlocal variable.
    gpg_id = option('gpg_id')

    manager = pyinotify.WatchManager()
    notifier = pyinotify.ThreadedNotifier(manager, EventHandler())
    notifier.start()
    tmpdir = os.path.dirname(fp.name)
    mask = pyinotify.IN_MODIFY  # pylint: disable=no-member
    watch = manager.add_watch(tmpdir, mask)
    click.edit(filename=fp.name, editor=option('editor'))
    manager.rm_watch(watch[tmpdir])
    notifier.stop()

    # Read the file one last time. It may have already been read
    # in the handler, but it's not guaranteed. If for example the
    # user saved and exited the editor, there is a race condition.
    fp.seek(0)
    updated = fp.read()
    try:
        data = to_dict(updated)
    except yaml.scanner.ScannerError:
        sys.exit("Invalid yaml")
    else:
        db.put(name, data)
        db.write(gpg_id)
    fp.close()


@cli.command()
@click.argument('names', nargs=-1, required=True, metavar='ENTRY/GROUP...')
@click.option('-f', '--force', is_flag=True,
              help="Do not prompt for confirmation.")
def rm(names, force):
    """Remove entries or groups."""
    db = DB()
    db.read(lock=True)
    if len(names) == 1:
        if db.pop(names[0], force) is None:
            sys.exit("%s not found" % names[0])
        db.write()
        return

    confirm("Delete %s arguments?" % len(names), force)

    for name in names:
        if db.pop(name, force=True) is None:
            sys.exit("%s not found" % name)

    db.write()


@cli.command(short_help="Move or rename entries.")
@click.argument('source', nargs=-1, required=True)
@click.argument('dest', metavar='DEST/GROUP')
@click.option('-f', '--force', is_flag=True,
              help="Do not prompt for confirmation.")
def mv(source, dest, force):
    """Rename SOURCE to DEST or move SOURCE(s) to GROUP."""
    db = DB()
    db.read(lock=True)
    if len(source) > 1 and not isgroup(dest):
        sys.exit("%s is not a group" % dest)

    if len(source) == 1 and isgroup(source[0]):
        if not isgroup(dest):
            sys.exit("%s is not a group" % dest)
        groupname = source[0]
        if db.get(groupname) is None:
            sys.exit("%s not found" % groupname)
        if db.get(dest) is not None:
            # Do not implicitly remove a whole group even by asking the
            # user. Instead we could prompt for merging the two groups.
            sys.exit("%s already exists" % dest)
        group = db.pop(groupname, force=True)
        db.put(dest, group)
    else:
        for name in source:
            if db.get(name) is None:
                sys.exit("%s not found" % name)
            # os.path.join() because using '/'.join('groupname/', 'entryname')
            # would result in two slashes.
            newname = os.path.join(dest, split(name)[1]) \
                if isgroup(dest) else dest
            if db.get(newname) is not None:
                confirm("Overwrite %s?" % newname, force)
            entry = db.pop(name, force=True)
            db.put(newname, entry)

    db.write()


# Autotype
def active_window():  # pragma: no cover
    """Get active window id and name."""
    window_id = out(['xdotool', 'getactivewindow'])
    window_name = out(['xdotool', 'getwindowname', window_id])
    return window_id, window_name


def keyboard(key, entry):
    """Simulate keyboard input for `key` using xdotool."""
    if key[0] == '<' and key[-1] == '>':
        value = entry.get(key[1:-1])
        if not value:
            die("%s not found" % key[1:-1])
        # `value` could be an int so we explicitly convert it to str
        call(['xdotool', 'type', '--clearmodifiers', str(value)])
    elif key[0] == '!':
        duration = float(key[1:])
        time.sleep(duration)
    else:
        call(['xdotool', 'key', key])


def get_autotype(entry):
    """Return a list with the items that need to be typed."""
    data = entry.get('autotype')
    if not data:
        if entry.get('username') and entry.get('password'):
            data = '<username> Tab <password> Return'
        elif entry.get('password'):
            data = '<password> Return'
        else:
            die("Don't know what to type :(")

    return data.split()


@cli.command()
def autotype():
    """Type login credentials."""
    db = DB()
    db.read()
    window = active_window()

    # Put the entries that match the window title in `matches`, and every entry
    # in `names`, to fall back to that if there are no matches.
    names = []
    matches = []
    for groupname, entryname in db:
        name = '%s/%s' % (groupname, entryname)
        names.append(name)
        keywords = [entryname.lower()] + db.keywords(name)
        title = window[1].lower()
        if any(keyword in title for keyword in keywords):
            matches.append(name)

    if len(matches) == 1:
        choice = matches[0].strip()
    else:
        command = option('dmenu')
        choices = '\n'.join(sorted(matches if matches else names))
        choice = out(command, input=choices).strip()

    entry = db.get(choice)
    for key in get_autotype(entry):
        if active_window() != window:  # pragma: no cover
            die("Window has changed")
        keyboard(key, entry)


if __name__ == '__main__':
    cli()  # pylint: disable=no-value-for-parameter
