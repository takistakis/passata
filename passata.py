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
        die(e)
    except FileNotFoundError:
        die("Executable '%s' not found" % command[0])


def out(command, input=None):
    """Run command, optionally passing `input` to stdin, and return output.

    The output usually comes back with a trailing newline and it needs to be
    striped if not needed.
    """
    return call(command, stdout=subprocess.PIPE, input=input)


def echo(message):  # pragma: no cover
    """Print message to stdout or via a pager if it doesn't fit on screen."""
    # Plus one line for the prompt
    if message.count('\n') + 1 >= click.get_terminal_size()[1]:
        click.echo_via_pager(message)
    else:
        click.echo(message)


def die(message):
    """Print given message to stderr and exit."""
    click.echo(message, file=sys.stderr)
    sys.exit(1)


def xdie(message):
    """Send a notification with given message and exit."""
    icon = 'dialog-warning'
    call(['notify-send', '-i', icon, 'passata', message])
    sys.exit(1)


def lock_file(path):
    """Open a file and lock it.

    By locking the database, we can assure that only one passata
    process that is executing a database modifying command, can be
    running at a time. Read-only commands should not acquire the lock.
    """
    # Open with 'a' (i.e. append) to prevent truncation
    lock = open(path, 'a')
    try:
        fcntl.lockf(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
    except IOError:
        die("Another passata process is editing the database")

    # Register the lock file's file descriptor to prevent it from closing
    click.get_current_context().obj['_lock'] = lock


def to_clipboard(data, loops=0):
    """Add `data` to clipbord until pasted `loops` times."""
    command = ['xclip', '-selection', 'clipboard', '-loops', str(loops)]
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
            die("%s is nested too deeply" % name)

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
        'font': None,
        'length': 20,
        'entropy': None,
        'symbols': True,
        'color': True,
    }
    try:
        with open(confpath) as f:
            data = f.read()
    except FileNotFoundError:
        die("Run `passata init` first")

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
        "# font: Font to use for dmenu\n"
        "# length: Default length of generated passwords [default: 20]\n"
        "# entropy: Calculate length for given bits of entropy\n"
        "# symbols: Whether to use symbols in the generated password "
        "[default: true]\n"
        "# color: Whether to colorize the output [default: true]\n"
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
        die("No gpg secret keys found")
    return gpg_ids.group(1)


# Database
def decrypt(path):  # pragma: no cover
    """Decrypt the contents of the given file using gpg."""
    return out(['gpg', '-d', path])


def read_db(lock=False):
    """Return the database as a plaintext string."""
    dbpath = os.path.expanduser(option('database'))
    if not os.path.isfile(dbpath):
        die("Database file (%s) does not exist" % dbpath)
    if lock:
        lock_file(dbpath)
    data = decrypt(dbpath)
    return to_dict(data)


def encrypt(data):  # pragma: no cover
    """Encrypt given text using gpg."""
    gpg_id = option('gpg_id')
    return out(['gpg', '-ear', gpg_id], input=data)


def write_db(db, force=True):
    """Write the database as an encrypted string."""
    dbpath = os.path.expanduser(option('database'))
    confirm_overwrite(dbpath, force)
    data = to_string(db)
    encrypted = encrypt(data)
    # Write to a temporary file, make sure the data has reached the
    # disk and replace the database with the temporary file using
    # os.replace() which is guaranteed to be an atomic operation.
    fd = tempfile.NamedTemporaryFile(
        mode='w', dir=os.path.dirname(dbpath), delete=False)
    fd.write(encrypted)
    fd.flush()
    os.fsync(fd.fileno())
    fd.close()
    os.replace(fd.name, dbpath)
    # Here the lock on the database is released


def get(db, name):
    """Return database, group or entry."""
    groupname, entryname = split(name)

    # Get the whole database
    if not groupname:
        return db

    # Get whole group
    if not entryname:
        return db.get(groupname)

    # Get single entry
    if groupname not in db:
        return None

    return db[groupname].get(entryname)


def put(db, name, subdict):
    """Add or replace subdict creating group if needed."""
    # Remove if given empty dict
    if not subdict:
        pop(db, name)
        return

    groupname, entryname = split(name)

    # Put the whole database
    if not groupname:
        # `db = subdict` wouldn't work because it makes a local copy
        # of `subdict` and the `db` dict of the caller stays the same.
        db.clear()
        db.update(subdict)

    # Put a whole group
    elif not entryname:
        db[groupname] = subdict

    # Put a single entry
    else:
        if groupname not in db:
            db[groupname] = collections.OrderedDict()
        db[groupname][entryname] = subdict


def pop(db, name, force=False):
    """Remove subdict and every empty parent and return it."""
    groupname, entryname = split(name)

    # Remove the whole database
    if not groupname:
        confirm("Delete the whole database?", force)
        db.clear()
        # Maybe we should copy and return the original db for consistency but
        # it's not needed anywhere.
        return None

    # Group should exist
    if groupname not in db:
        return None

    # Remove whole group
    if not entryname:
        confirm("Delete group '%s'?" % groupname, force)
        return db.pop(groupname)

    # Entry should exist
    if entryname not in db[groupname]:
        return None

    # Remove entry
    confirm("Delete '%s/%s'?" % (groupname, entryname), force)
    entry = db[groupname].pop(entryname)
    if not db[groupname]:
        del db[groupname]
    return entry


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
    # lock_file() creates the file if it does not
    # exist, so we need to ask for confirmation here.
    confirm_overwrite(dbpath, force)
    lock_file(dbpath)
    confpath = obj['_confpath']
    config = {'database': dbpath, 'gpg_id': gpg_id}
    write_config(confpath, config, force)
    obj.update(config)
    write_db(collections.OrderedDict())


@cli.command()
@click.option('-n', '--no-tree', is_flag=True,
              help="Print entries in 'groupname/entryname' format.")
@click.option('--color/--no-color', is_flag=True,
              default=lambda: option('color'),
              help="Whether to colorize the output.")
@click.argument('group', required=False)
def ls(group, no_tree, color):
    """List entries in a tree-like format."""
    db = read_db()
    lines = []
    if group:
        groupname = group.rstrip('/')
        if groupname not in db:
            die("%s not found" % groupname)
        for entryname in db[groupname]:
            lines.append(entryname)
    elif no_tree:
        for groupname in db:
            for entryname in db[groupname]:
                lines.append("%s/%s" % (groupname, entryname))
    else:
        for groupname in db:
            lines.append(click.style(groupname, fg='blue', bold=True)
                         if color else groupname)
            entrynames = list(db[groupname])
            for entryname in entrynames[:-1]:
                lines.append("├── %s" % entryname)
            lines.append("└── %s" % entrynames[-1])
    if lines:
        echo('\n'.join(lines))


@cli.command(short_help="Show entry, group or the whole database.")
@click.option('-c', '--clipboard', is_flag=True,
              help="Copy password to clipboard instead of printing.")
@click.option('--color/--no-color', is_flag=True,
              default=lambda: option('color'),
              help="Whether to colorize the output.")
@click.argument('name', required=False)
def show(name, clipboard, color):
    """Decrypt and print the contents of NAME.

    NAME can be an entry, a group, or omitted to print the whole database. If
    NAME is an entry and --clipboard is specified, the password will stay in
    the clipboard until it is pasted.
    """
    db = read_db()
    entry = get(db, name)
    if entry is None:
        die("%s not found" % name)

    if clipboard:
        if name is None:
            die("Can't put the entire database to clipboard")
        if isgroup(name):
            die("Can't put the entire group to clipboard")
        to_clipboard(entry['password'], loops=1)
    else:
        data = to_string(entry).strip()
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
        echo(data)


def do_insert(name, password, force):
    """Insert `password` into `name` without deleting everything else.

    If `name` is already in the database, keep a backup of the old password.
    Return the old password or None if there wasn't one.
    """
    if isgroup(name):
        die("%s is a group" % name)
    db = read_db(lock=True)
    entry = get(db, name)
    old_password = None
    if entry is None:
        put(db, name, {'password': password})
    else:
        confirm("Overwrite %s?" % name, force)
        if 'password' in entry:
            old_password = entry['password']
            entry['old_password'] = old_password
        entry['password'] = password

    write_db(db)
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


def generate_password(length, entropy, symbols, force):
    """Generate a random password."""
    choice = random.SystemRandom().choice
    chargroups = [string.ascii_letters, string.digits]
    if symbols:
        chargroups.append(string.punctuation)
    chars = ''.join(chargroups)
    if entropy is not None:
        length = math.ceil(entropy / math.log2(len(chars)))
        entropy = math.log2(len(chars) ** length)
    else:
        entropy = math.log2(len(chars) ** length)
    if entropy < 32:
        msg = "Generate password with only %.3f bits of entropy?" % entropy
        confirm(msg, force)
    password = ''.join(choice(chars) for i in range(length))
    click.echo("Generated password with %.3f bits of entropy" % entropy)
    return password


@cli.command()
@click.argument('name', required=False)
@click.option('-f', '--force', is_flag=True,
              help="Do not prompt for confirmation.")
@click.option('-c', '--clipboard', is_flag=True,
              help="Copy password to clipboard instead of printing.")
@click.option('-l', '--length', type=int, default=lambda: option('length'),
              help="Length of the generated password.")
@click.option('-e', '--entropy', type=int, default=lambda: option('entropy'),
              help="Calculate length for given bits of entropy.")
@click.option('--symbols/--no-symbols', is_flag=True,
              default=lambda: option('symbols'),
              help="Whether to use symbols in the generated password.")
def generate(name, force, clipboard, length, entropy, symbols):
    """Generate a random password.

    When overwriting an existing entry, the old password is kept in
    <old_password>.
    """
    password = generate_password(length, entropy, symbols, force)
    old_password = do_insert(name, password, force) if name else None
    if clipboard:
        if old_password is not None:
            to_clipboard(old_password, loops=1)
            click.echo("Put old password to clipboard "
                       "(will disappear after pasted)")
            click.pause()
        to_clipboard(password, loops=2)
        click.echo("Put generated password to clipboard "
                   "(will disappear after pasted twice)")
    else:
        click.echo(password)


@cli.command()
@click.argument('name', required=False)
def edit(name):
    """Edit entry, group or the whole database."""
    db = read_db(lock=True)
    subdict = get(db, name) or collections.OrderedDict()
    original = to_string(subdict)
    # Describe what is being edited in a comment at the top
    comment = name or "passata database"
    text = "# %s\n%s" % (comment, original)
    updated = click.edit(text, editor=option('editor'), extension='.yml')
    # If not saved or saved but unchanged do nothing
    if updated is None or original == updated.strip():
        return
    put(db, name, to_dict(updated))
    write_db(db)


@cli.command()
@click.argument('names', nargs=-1, required=True, metavar='ENTRY/GROUP...')
@click.option('-f', '--force', is_flag=True,
              help="Do not prompt for confirmation.")
def rm(names, force):
    """Remove entries or groups."""
    db = read_db(lock=True)
    if len(names) == 1:
        if pop(db, names[0], force) is None:
            die("%s not found" % names[0])
        write_db(db)
        return

    confirm("Delete %s arguments?" % len(names), force)

    for name in names:
        if pop(db, name, force=True) is None:
            die("%s not found" % name)

    write_db(db)


@cli.command(short_help="Move or rename entries.")
@click.argument('source', nargs=-1, required=True)
@click.argument('dest', metavar='DEST/GROUP')
@click.option('-f', '--force', is_flag=True,
              help="Do not prompt for confirmation.")
def mv(source, dest, force):
    """Rename SOURCE to DEST or move SOURCE(s) to GROUP."""
    db = read_db(lock=True)
    if len(source) > 1 and not isgroup(dest):
        die("%s is not a group" % dest)

    if len(source) == 1 and isgroup(source[0]):
        if not isgroup(dest):
            die("%s is not a group" % dest)
        groupname = source[0]
        if get(db, groupname) is None:
            die("%s not found" % groupname)
        if get(db, dest) is not None:
            # Do not implicitly remove a whole group even by asking the
            # user. Instead we could prompt for merging the two groups.
            die("%s already exists" % dest)
        group = pop(db, groupname, force=True)
        put(db, dest, group)
    else:
        for name in source:
            if get(db, name) is None:
                die("%s not found" % name)
            # os.path.join() because using '/'.join('groupname/', 'entryname')
            # would result in two slashes.
            newname = os.path.join(dest, split(name)[1]) \
                if isgroup(dest) else dest
            if get(db, newname) is not None:
                confirm("Overwrite %s?" % newname, force)
            entry = pop(db, name, force=True)
            put(db, newname, entry)

    write_db(db)


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
            xdie("%s not found" % key[1:-1])
        # `value` could be an int so we explicitly convert it to str
        call(['xdotool', 'type', '--clearmodifiers', str(value)])
    elif key[0] == '!':
        duration = float(key[1:])
        time.sleep(duration)
    else:
        call(['xdotool', 'key', key])


def get_keywords(entry):
    """Return a list of strings to search for in the window's title."""
    keywords = entry.get('keywords')
    if isinstance(keywords, list):
        return [str(keyword).lower() for keyword in keywords]
    elif keywords is not None:
        return [str(keywords).lower()]
    return []


def get_autotype(entry):
    """Return a list with the items that need to be typed."""
    data = entry.get('autotype')
    if not data:
        if entry.get('username') and entry.get('password'):
            data = '<username> Tab <password> Return'
        elif entry.get('password'):
            data = '<password> Return'
        else:
            xdie("Don't know what to type :(")

    return data.split()


@cli.command()
def autotype():
    """Type login credentials."""
    db = read_db()
    window = active_window()

    # Put the entries that match the window title in `matches`, and every entry
    # in `names`, to fall back to that if there are no matches.
    names = []
    matches = []
    for groupname in sorted(db):
        for entryname in sorted(db[groupname]):
            name = '%s/%s' % (groupname, entryname)
            names.append(name)
            entry = get(db, name)
            keywords = [entryname.lower()]
            keywords.extend(get_keywords(entry))
            title = window[1].lower()
            if any(keyword in title for keyword in keywords):
                matches.append(name)

    if len(matches) == 1:
        choice = matches[0].strip()
    else:
        font = option('font')
        command = ['dmenu'] if font is None else ['dmenu', '-fn', font]
        choices = '\n'.join(sorted(matches if matches else names))
        choice = out(command, input=choices).strip()

    entry = get(db, choice)
    for key in get_autotype(entry):
        if active_window() != window:  # pragma: no cover
            xdie("Window has changed")
        keyboard(key, entry)


if __name__ == '__main__':
    cli()  # pylint: disable=no-value-for-parameter
