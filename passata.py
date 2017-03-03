#!/usr/bin/env python3

# Copyright 2017 Panagiotis Ktistakis <panktist@gmail.com>
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program.  If not, see <http://www.gnu.org/licenses/>.

"""A simple password manager, inspired by pass."""

import fcntl
import os
import random
import re
import string
import subprocess
import sys
import time

import click
import yaml

__version__ = '0.1.0'


# Utilities
def call(command, stdout=None, input=None):
    """Run command, optionally passing `input` to stdin.

    By default, standard output is printed and ignored and None is return.
    Setting stdout=subprocess.PIPE, will capture and return standard output
    instead.
    """
    # This could be achieved more easily with subprocess.run(), but it is
    # available since python 3.5 and we want to keep compatibility with at
    # least Debian stable which is currently on version 3.4.
    kwargs = {
        'stdin': subprocess.PIPE if input is not None else None,
        'stdout': stdout,
        'stderr': subprocess.DEVNULL,
        'universal_newlines': True
    }
    try:
        with subprocess.Popen(command, **kwargs) as process:
            output = process.communicate(input)[0]
            retcode = process.poll()
            if retcode != 0:
                message = "Command '%s' returned non-zero exit status %d"
                die(message % (' '.join(command), retcode))
    except FileNotFoundError:
        die("Executable '%s' not found" % command[0])

    return output


def out(command, input=None):
    """Run command, optionally passing `input` to stdin, and return output.

    The output usually comes back with a trailing newline and it needs to be
    striped if not needed.
    """
    return call(command, stdout=subprocess.PIPE, input=input)


def die(message):
    """Print given message to stderr and exit."""
    click.echo(message, file=sys.stderr)
    sys.exit(1)


def xdie(message):
    """Send a notification with given message and exit."""
    icon = 'dialog-warning'
    call(['notify-send', '-i', icon, 'passata', message])
    sys.exit(1)


def acquire_lock():
    """Open a file and lock it.

    That way we can assure that only one passata process that is executing a
    database modifying command, can be running at a time. Read-only commands
    should not acquire the lock.
    """
    lock = open('/tmp/passata.lock', 'w')
    try:
        fcntl.lockf(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
    except IOError:
        die("Another passata process is editing the database")

    # Register the lock file's file descriptor to prevent it from closing
    click.get_current_context().obj['_lock'] = lock


def to_clipboard(string, loops=0):
    """Add `string` to clipbord until pasted `loops` times."""
    command = ['xclip', '-selection', 'clipboard', '-loops', str(loops)]
    call(command, input=string)


def generate_password(length, symbols):
    """Generate a random password."""
    choice = random.SystemRandom().choice
    chargroups = [string.ascii_letters, string.digits]
    if symbols:
        chargroups.append(string.punctuation)
    chars = ''.join(chargroups)
    password = ''.join(choice(chars) for i in range(length))
    return password


def confirm(message, force):
    """Exit if the user does not agree."""
    if not force and not click.confirm(message):
        sys.exit(0)


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
            die("Too much nesting")

    return groupname, entryname


def to_dict(data):
    """Turn yaml string to dict."""
    # Return empty dict for empty string or None
    return yaml.safe_load(data) if data else {}


def to_string(data):
    """Turn dict to yaml string."""
    # Return empty string for empty dict or None
    return yaml.safe_dump(
        data, default_flow_style=False, allow_unicode=True
    ) if data else ''


# Config
def read_config():
    """Read the configuration file and return it as a dict."""
    config = click.get_current_context().obj
    confpath = config['_confpath']
    try:
        with open(confpath) as f:
            data = f.read()
    except FileNotFoundError:
        die("Run `passata init` first")

    return to_dict(data)


def option(key):
    """Return the config option for `key`."""
    config = click.get_current_context().obj
    if key not in config:
        die("'%s' was not found in the configuration file" % key)
    return config[key]


def default_config_path():
    """Return the the default configuration path."""
    confdir = click.get_app_dir('passata')
    confpath = os.path.join(confdir, 'config.yml')
    return os.path.expanduser(confpath)


def default_gpg_id():
    """Return the id of the first gpg secret key."""
    command = ['gpg', '--list-secret-keys']
    gpg_ids = re.search(r'<(.*)>', out(command))
    return gpg_ids.group(1)


# Database
def decrypt(path):
    """Decrypt the contents of the given file using gpg."""
    return out(['gpg', '-d', path])


def read_db():
    """Return the database as a plaintext string."""
    dbpath = option('database')
    dbpath = os.path.expanduser(dbpath)
    if not os.path.isfile(dbpath):
        die("Database file (%s) does not exist" % dbpath)
    data = decrypt(dbpath)
    return to_dict(data)


def encrypt(data):
    """Encrypt given text using gpg."""
    gpg_id = option('gpg_id')
    return out(['gpg', '-ear', gpg_id], input=data)


def write_db(db, force=True):
    """Write the database as an encrypted string."""
    dbpath = option('database')
    if os.path.isfile(dbpath):
        confirm("Overwrite %s?" % dbpath, force)
    data = to_string(db)
    encrypted = encrypt(data)
    with open(dbpath, 'w') as f:
        f.write(encrypted)


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
            db[groupname] = {}
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
@click.group()
@click.option('--config', type=click.Path(dir_okay=False),
              default=default_config_path, envvar='PASSATA_CONFIG_PATH',
              help="Path of the configuration file.")
@click.version_option(version=__version__)
@click.pass_context
def cli(ctx, config):
    """A simple password manager, inspired by pass."""
    ctx.obj = {
        '_confpath': os.path.abspath(os.path.expanduser(config)),
        'editor': os.environ.get('EDITOR', 'vim'),
        'font': None,
        'length': 20,
        'symbols': True,
    }

    # When init is invoked there isn't supposed to be a config file yet
    if ctx.invoked_subcommand != 'init':
        ctx.obj.update(read_config())


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
    acquire_lock()
    dbpath = os.path.abspath(os.path.expanduser(path))
    confpath = obj['_confpath']
    if os.path.isfile(confpath):
        confirm("Overwrite %s?" % confpath, force)
    os.makedirs(os.path.dirname(confpath), exist_ok=True)

    template = (
        "# Configuration file for passata\n"
        "# Available options:\n"
        "# database: Path of the database file\n"
        "# gpg_id: GnuPG ID used for database encryption\n"
        "# editor: Editor used for editing database entries "
        "[default: EDITOR or vim]\n"
        "# font: Font to use for dmenu\n"
        "# length: Default length of generated passwords [default: 20]\n"
        "# symbols: Whether to use symbols in the generated password "
        "[default: true]\n"
        "%s"
    )

    config = {
        'database': dbpath,
        'gpg_id': gpg_id,
    }

    with open(confpath, 'w') as f:
        f.write(template % to_string(config))

    obj.update(config)
    write_db({}, force=False)


@cli.command()
@click.option('-n', '--no-tree', is_flag=True,
              help="Print entries in 'groupname/entryname' format.")
@click.argument('group', required=False)
def ls(group, no_tree):
    """List entries in a tree-like format."""
    db = read_db()
    if group:
        groupname = group.rstrip('/')
        if groupname not in db:
            die("%s not found" % groupname)
        for name in sorted(db[groupname]):
            click.echo(name)
    elif no_tree:
        for groupname in sorted(db):
            for entryname in sorted(db[groupname]):
                click.echo("%s/%s" % (groupname, entryname))
    else:
        for groupname in sorted(db):
            click.secho(groupname, fg='blue', bold=True)
            grouplist = sorted(db[groupname])
            for entryname in grouplist[:-1]:
                click.echo("├── %s" % entryname)
            click.echo("└── %s" % grouplist[-1])


@cli.command()
@click.option('-c', '--clipboard', is_flag=True,
              help="Copy password to clipboard instead of printing.")
@click.argument('name')
def show(name, clipboard):
    """Decrypt and print entry.

    If NAME is a group, print all entries in that group. If --clipboard is
    specified, the password will stay in the clipboard until it is pasted once.
    """
    db = read_db()
    entry = get(db, name)
    if entry is None:
        die("%s not found" % name)

    if clipboard:
        if isgroup(name):
            die("Can't put the entire group to clipboard")
        to_clipboard(entry['password'], loops=1)
    else:
        click.echo(to_string(entry).strip())


def do_insert(name, password, force):
    """Insert `password` into `name` without deleting everything else.

    If `name` is already in the database, keep a backup of the old password.
    """
    if isgroup(name):
        die("%s is a group" % name)
    db = read_db()
    entry = get(db, name)
    if entry is None:
        put(db, name, {'password': password})
    else:
        confirm("Overwrite %s?" % name, force)
        if 'password' in entry:
            entry['password_old'] = entry['password']
        entry['password'] = password

    write_db(db)


@cli.command()
@click.argument('name')
@click.option('-f', '--force', is_flag=True,
              help="Do not prompt for confirmation.")
@click.password_option(help="Give password instead of being prompted for it.")
def insert(name, force, password):
    """Insert a new password.

    When overwriting an existing entry, the old password is kept in
    <password_old>.
    """
    acquire_lock()
    do_insert(name, password, force)


@cli.command()
@click.argument('name', required=False)
@click.option('-f', '--force', is_flag=True,
              help="Do not prompt for confirmation.")
@click.option('-c', '--clipboard', is_flag=True,
              help="Copy password to clipboard instead of printing.")
@click.option('-l', '--length', type=click.IntRange(min=4), metavar='INT',
              default=lambda: option('length'),
              help="Length of the generated password.")
@click.option('--symbols/--no-symbols', is_flag=True,
              default=lambda: option('symbols'),
              help="Whether to use symbols in the generated password.")
def generate(name, force, clipboard, length, symbols):
    """Generate a random password.

    When overwriting an existing entry, the old password is kept in
    <password_old>. If --clipboard is specified, the password will stay in the
    clipboard until it is pasted twice.
    """
    acquire_lock()
    password = generate_password(length, symbols)
    if name:
        do_insert(name, password, force)
    if clipboard:
        to_clipboard(password, loops=2)
    else:
        click.echo(password)


@cli.command()
@click.argument('name', required=False)
def edit(name):
    """Edit entry, group or the whole database."""
    acquire_lock()
    db = read_db()
    subdict = get(db, name) or {}
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
    acquire_lock()
    db = read_db()
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
    acquire_lock()
    db = read_db()
    if len(source) > 1 and not isgroup(dest):
        die("%s is not a group" % dest)

    for name in source:
        if get(db, name) is None:
            die("%s not found" % name)
        # os.path.join() because using '/'.join('groupname/', 'entryname')
        # would result in two slashes.
        newname = os.path.join(dest, split(name)[1]) if isgroup(dest) else dest
        if get(db, newname) is not None:
            confirm("Overwrite %s?" % dest, force)
        entry = pop(db, name, force=True)
        put(db, newname, entry)

    write_db(db)


# Autotype
def active_window():
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


def get_autotype(entry):
    """Return a list with the items that need to be typed."""
    string = entry.get('autotype')
    if not string:
        if entry.get('username') and entry.get('password'):
            string = '<username> Tab <password> Return'
        elif entry.get('password'):
            string = '<password> Return'
        else:
            xdie("Don't know what to type :(")

    return string.split()


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
            if entryname.lower() in window[1].lower():
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
        if active_window() != window:
            xdie("Window has changed")
        keyboard(key, entry)


if __name__ == '__main__':
    cli()
