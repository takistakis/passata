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

"""Tests for passata."""

import os

import click
import click.testing
import pytest

import passata


@pytest.fixture
def db(tmpdir, monkeypatch):
    monkeypatch.setattr(passata, 'encrypt', lambda x: x)
    monkeypatch.setattr(passata, 'decrypt', lambda x: open(x).read())

    confpath = tmpdir.join('config.yml')
    dbpath = tmpdir.join('passata.db')

    confpath.write('database: %s\n'
                   'gpg_id: id\n' % dbpath)

    dbpath.write('internet:\n'
                 '  facebook:\n'
                 '    password: fb\n'
                 '    username: sakis\n'
                 '  github:\n'
                 '    password: gh\n'
                 '    username: takis\n')

    os.environ['PASSATA_CONFIG_PATH'] = str(confpath)

    yield dbpath


def read(dbpath):
    return open(str(dbpath)).read()


def run(args):
    runner = click.testing.CliRunner()
    return runner.invoke(passata.cli, args)


def clipboard():
    command = ['xclip', '-o', '-selection', 'clipboard']
    return passata.out(command)


def test_invalid_call():
    with pytest.raises(SystemExit):
        passata.call(['there_is_no_such_executable.exe'])


def test_init(tmpdir, monkeypatch):
    monkeypatch.setattr(passata, 'encrypt', lambda x: x)
    monkeypatch.setattr(passata, 'decrypt', lambda x: open(x).read())

    confpath = tmpdir.join('config.yml')
    dbpath = tmpdir.join('passata.db')

    # Try to execute a command without having initialized passata
    result = run(['--config', str(confpath), 'ls'])
    assert repr(result.exception) == 'SystemExit(1,)'
    assert result.output == "Run `passata init` first\n"
    assert not os.path.isfile(str(dbpath))

    # Initialize. It should not ask for confirmation.
    email = 'mail@mail.com'
    result = run(['--config=%s' % str(confpath), 'init',
                  '--gpg-id=%s' % email, '--path=%s' % dbpath])
    assert result.exit_code == 0
    assert result.exception is None
    assert result.output == ''
    assert os.path.isfile(str(dbpath))
    contents = confpath.read()
    assert 'database: %s' % dbpath in contents
    assert 'gpg_id: %s' % email in contents

    # Initialize again. Now it should ask for confirmation.
    monkeypatch.setattr(click, 'confirm', lambda m: confirm)
    confirm = False
    email2 = 'anothermail@mail.com'
    result = run(['--config=%s' % str(confpath), 'init',
                  '--gpg-id=%s' % email2, '--path=%s' % dbpath])
    contents = confpath.read()
    assert 'gpg_id: %s' % email in contents
    assert 'gpg_id: %s' % email2 not in contents

    # Try to execute a command again and now it should work
    result = run(['--config', str(confpath), 'ls'])
    assert result.exit_code == 0
    assert result.exception is None
    assert result.output == ''

    # Try again after deleting the database and it should fail
    os.unlink(str(dbpath))
    result = run(['--config', str(confpath), 'ls'])
    assert repr(result.exception) == 'SystemExit(1,)'
    assert result.output == "Database file (%s) does not exist\n" % dbpath


def test_ls(db):
    # List all
    result = run(['ls'])
    assert result.output == (
        'internet\n'
        '├── facebook\n'
        '└── github\n'
    )

    # List group
    result = run(['ls', 'internet'])
    assert result.output == (
        'facebook\n'
        'github\n'
    )

    # --no-tree
    result = run(['ls', '--no-tree'])
    assert result.output == (
        'internet/facebook\n'
        'internet/github\n'
    )

    # Nonexistent group
    result = run(['ls', 'nonexistent'])
    assert repr(result.exception) == 'SystemExit(1,)'


def test_show(db):
    # Normal show
    result = run(['show', 'internet/github'])
    assert result.output == (
        'password: gh\n'
        'username: takis\n'
    )

    # Try to show a nonexistent entry
    result = run(['show', 'internet/nonexistent'])
    assert repr(result.exception) == 'SystemExit(1,)'
    assert result.output == "internet/nonexistent not found\n"

    # Try to show an entry three levels deep
    result = run(['show', 'one/two/three'])
    assert repr(result.exception) == 'SystemExit(1,)'

    # Clipboard
    result = run(['show', 'internet/github', '--clipboard'])
    assert result.output == ''
    assert clipboard() == 'gh'
    # Should be gone after being pasted
    with pytest.raises(SystemExit):
        clipboard()

    # Try to put the whole database to clipboard
    result = run(['show', '--clipboard'])
    assert repr(result.exception) == 'SystemExit(1,)'
    assert result.output == "Can't put the entire database to clipboard\n"

    # Try to put a whole group to clipboard
    result = run(['show', 'internet', '--clipboard'])
    assert repr(result.exception) == 'SystemExit(1,)'
    assert result.output == "Can't put the entire group to clipboard\n"

    # Show group
    expected = (
        'facebook:\n'
        '  password: fb\n'
        '  username: sakis\n'
        'github:\n'
        '  password: gh\n'
        '  username: takis\n'
    )
    result = run(['show', 'internet'])
    assert result.output == expected

    # Show group with trailing slash
    result = run(['show', 'internet/'])
    assert result.output == expected


def test_insert(monkeypatch, db):
    monkeypatch.setattr(click, 'confirm', lambda m: confirm)

    # Try to insert group
    result = run(['insert', 'group', '--password=...'])
    assert repr(result.exception) == 'SystemExit(1,)'

    # Insert entry
    run(['insert', 'group/test', '--password=one'])
    assert read(db) == (
        'internet:\n'
        '  facebook:\n'
        '    password: fb\n'
        '    username: sakis\n'
        '  github:\n'
        '    password: gh\n'
        '    username: takis\n'
        'group:\n'
        '  test:\n'
        '    password: one\n'
    )

    # Force update
    run(['insert', 'group/test', '--force', '--password=two'])
    assert read(db) == (
        'internet:\n'
        '  facebook:\n'
        '    password: fb\n'
        '    username: sakis\n'
        '  github:\n'
        '    password: gh\n'
        '    username: takis\n'
        'group:\n'
        '  test:\n'
        '    password: two\n'
        '    old_password: one\n'
    )

    # Confirm update
    confirm = True
    run(['insert', 'group/test', '--password=three'])
    assert read(db) == (
        'internet:\n'
        '  facebook:\n'
        '    password: fb\n'
        '    username: sakis\n'
        '  github:\n'
        '    password: gh\n'
        '    username: takis\n'
        'group:\n'
        '  test:\n'
        '    password: three\n'
        '    old_password: two\n'
    )

    # Do not confirm update
    confirm = False
    result = run(['insert', 'group', '--password=four'])
    assert repr(result.exception) == 'SystemExit(1,)'

    # Add an entry with no password so there's no need for a backup
    monkeypatch.setattr(click, 'edit', lambda x, editor, extension: updated)
    updated = 'username: user\n'
    run(['edit', 'group/test'])
    run(['insert', 'group/test', '--force', '--password=five'])
    assert read(db) == (
        'internet:\n'
        '  facebook:\n'
        '    password: fb\n'
        '    username: sakis\n'
        '  github:\n'
        '    password: gh\n'
        '    username: takis\n'
        'group:\n'
        '  test:\n'
        '    username: user\n'
        '    password: five\n'
    )


def test_generate_password():
    alphanumeric = ('abcdefghijklmnopqrstuvwxyz'
                    'ABCDEFGHIJKLMNOPQRSTUVWXYZ'
                    '0123456789')
    symbols = '!"#$%&\'()*+,-./:;<=>?@[\]^_`{|}~'

    password = passata.generate_password(10, False)
    assert len(password) == 10
    assert all(char in alphanumeric for char in password)

    password = passata.generate_password(17, True)
    assert len(password) == 17
    assert all(char in alphanumeric + symbols for char in password)


def test_generate(monkeypatch, db):
    monkeypatch.setattr(passata, 'generate_password', lambda l, s: l * 'x')

    # Too short
    result = run(['generate', '--length=2'])
    assert result.exit_code == 2
    assert 'Error' in result.output

    # Generate and print
    result = run(['generate'])
    assert result.output == 'xxxxxxxxxxxxxxxxxxxx\n'

    # Generate and put to clipboard
    result = run(['generate', '--clipboard'])
    assert result.output == ("Put generated password to clipboard "
                             "(will disappear after pasted twice)\n")
    assert clipboard() == 'xxxxxxxxxxxxxxxxxxxx'
    assert clipboard() == 'xxxxxxxxxxxxxxxxxxxx'
    with pytest.raises(SystemExit):
        clipboard()

    # Generate, put in new entry and print
    result = run(['generate', 'asdf/test', '--length=5', '--force'])
    assert result.output == 'xxxxx\n'

    # Generate, put in existing entry and put to clipboard
    monkeypatch.setattr(click, 'pause',
                        lambda: print("Press any key to continue ..."))
    result = run(['generate', 'asdf/test', '--length=7', '--force',
                  '--clipboard'])
    assert result.output == ("Put old password to clipboard "
                             "(will disappear after pasted)\n"
                             "Press any key to continue ...\n"
                             "Put generated password to clipboard "
                             "(will disappear after pasted twice)\n")
    assert clipboard() == 'xxxxxxx'
    assert clipboard() == 'xxxxxxx'
    with pytest.raises(SystemExit):
        clipboard()

    assert read(db) == (
        'internet:\n'
        '  facebook:\n'
        '    password: fb\n'
        '    username: sakis\n'
        '  github:\n'
        '    password: gh\n'
        '    username: takis\n'
        'asdf:\n'
        '  test:\n'
        '    password: xxxxxxx\n'
        '    old_password: xxxxx\n'
    )


def test_edit_entry(monkeypatch, db):
    monkeypatch.setattr(click, 'edit', lambda x, editor, extension: updated)
    monkeypatch.setattr(click, 'confirm', lambda m: confirm)

    updated = (
        'username: takis\n'
        'password: secret\n'
    )
    run(['edit', 'internet/reddit'])
    assert read(db) == (
        'internet:\n'
        '  facebook:\n'
        '    password: fb\n'
        '    username: sakis\n'
        '  github:\n'
        '    password: gh\n'
        '    username: takis\n'
        '  reddit:\n'
        '    username: takis\n'
        '    password: secret\n'
    )

    updated = ''
    confirm = True
    run(['edit', 'internet/reddit'])
    assert read(db) == (
        'internet:\n'
        '  facebook:\n'
        '    password: fb\n'
        '    username: sakis\n'
        '  github:\n'
        '    password: gh\n'
        '    username: takis\n'
    )

    updated = (
        'username: sakis\n'
        'password: yolo\n'
    )
    run(['edit', 'mail/gmail'])
    assert read(db) == (
        'internet:\n'
        '  facebook:\n'
        '    password: fb\n'
        '    username: sakis\n'
        '  github:\n'
        '    password: gh\n'
        '    username: takis\n'
        'mail:\n'
        '  gmail:\n'
        '    username: sakis\n'
        '    password: yolo\n'
    )

    updated = ''
    confirm = False
    run(['edit', 'mail/gmail'])
    assert read(db) == (
        'internet:\n'
        '  facebook:\n'
        '    password: fb\n'
        '    username: sakis\n'
        '  github:\n'
        '    password: gh\n'
        '    username: takis\n'
        'mail:\n'
        '  gmail:\n'
        '    username: sakis\n'
        '    password: yolo\n'
    )

    updated = ''
    confirm = True
    run(['edit', 'mail/gmail'])
    assert read(db) == (
        'internet:\n'
        '  facebook:\n'
        '    password: fb\n'
        '    username: sakis\n'
        '  github:\n'
        '    password: gh\n'
        '    username: takis\n'
    )

    # Cover the possibility of leaving empty an already empty entry
    updated = ''
    confirm = True
    run(['edit', 'asdf/asdf'])
    assert read(db) == (
        'internet:\n'
        '  facebook:\n'
        '    password: fb\n'
        '    username: sakis\n'
        '  github:\n'
        '    password: gh\n'
        '    username: takis\n'
    )


def test_edit_group(monkeypatch, db):
    monkeypatch.setattr(click, 'edit', lambda x, editor, extension: updated)
    monkeypatch.setattr(click, 'confirm', lambda m: confirm)

    updated = ''
    confirm = False
    run(['edit', 'internet'])
    assert read(db) == (
        'internet:\n'
        '  facebook:\n'
        '    password: fb\n'
        '    username: sakis\n'
        '  github:\n'
        '    password: gh\n'
        '    username: takis\n'
    )

    updated = ''
    confirm = True
    run(['edit', 'internet'])
    assert read(db) == ''

    # Cover the possibility of leaving empty an already empty group
    updated = ''
    confirm = True
    run(['edit', 'asdf'])
    assert read(db) == ''

    updated = (
        'facebook:\n'
        '  username: takis\n'
        '  password: secret\n'
    )
    run(['edit', 'internet'])
    assert read(db) == (
        'internet:\n'
        '  facebook:\n'
        '    username: takis\n'
        '    password: secret\n'
    )


def test_edit_database(monkeypatch, db):
    monkeypatch.setattr(click, 'edit', lambda x, editor, extension: updated)
    monkeypatch.setattr(click, 'confirm', lambda m: confirm)

    updated = (
        'internet:\n'
        '  facebook:\n'
        '    password: fb\n'
        '    username: sakis\n'
    )
    confirm = True
    run(['edit'])
    assert read(db) == updated

    original = read(db)
    updated = ''
    confirm = False
    run(['edit'])
    assert read(db) == original

    updated = ''
    confirm = True
    run(['edit'])
    assert read(db) == ''


def test_rm_entry(monkeypatch, db):
    # Normal removal
    run(['rm', '--force', 'internet/facebook'])
    assert read(db) == (
        'internet:\n'
        '  github:\n'
        '    password: gh\n'
        '    username: takis\n'
    )

    # Remove nonexistent entry
    result = run(['rm', 'internet/nonexistent'])
    assert repr(result.exception) == 'SystemExit(1,)'

    # Do not confirm removal
    monkeypatch.setattr(click, 'confirm', lambda m: False)
    run(['rm', 'internet/github'])
    assert read(db) == (
        'internet:\n'
        '  github:\n'
        '    password: gh\n'
        '    username: takis\n'
    )

    # Remove last entry
    run(['rm', '--force', 'internet/github'])
    assert read(db) == ''


def test_rm_entries(db):
    run(['rm', '--force', 'internet/facebook', 'internet/github'])
    assert read(db) == ''

    result = run(['rm', '--force', 'asdf/asdf', 'asdf/asdf2'])
    assert repr(result.exception) == 'SystemExit(1,)'


def test_rm_group(db):
    result = run(['rm', '--force', 'asdf'])
    assert repr(result.exception) == 'SystemExit(1,)'

    run(['rm', '--force', 'internet'])
    assert read(db) == ''


def test_mv_entry_to_entry(db):
    run(['mv', 'internet/facebook', 'internet/fb'])
    assert read(db) == (
        'internet:\n'
        '  github:\n'
        '    password: gh\n'
        '    username: takis\n'
        '  fb:\n'
        '    password: fb\n'
        '    username: sakis\n'
    )


def test_mv_entry_to_group(db):
    run(['mv', 'internet/facebook', 'new'])
    assert read(db) == (
        'internet:\n'
        '  github:\n'
        '    password: gh\n'
        '    username: takis\n'
        'new:\n'
        '  facebook:\n'
        '    password: fb\n'
        '    username: sakis\n'
    )


def test_mv_entries_to_entry(db):
    result = run(['mv', 'internet/facebook', 'internet/github', 'new/new'])
    assert repr(result.exception) == 'SystemExit(1,)'


def test_mv_entries_to_group(db):
    run(['mv', 'internet/facebook', 'internet/github', 'new'])
    assert read(db) == (
        'new:\n'
        '  facebook:\n'
        '    password: fb\n'
        '    username: sakis\n'
        '  github:\n'
        '    password: gh\n'
        '    username: takis\n'
    )


def test_mv_nonexistent_entry(db):
    result = run(['mv', 'internet/nonexistent', 'group'])
    assert repr(result.exception) == 'SystemExit(1,)'


def test_mv_overwrite(monkeypatch, db):
    monkeypatch.setattr(click, 'confirm', lambda m: confirm)

    confirm = False
    run(['mv', 'internet/facebook', 'internet/github'])
    assert read(db) == (
        'internet:\n'
        '  facebook:\n'
        '    password: fb\n'
        '    username: sakis\n'
        '  github:\n'
        '    password: gh\n'
        '    username: takis\n'
    )

    confirm = True
    run(['mv', 'internet/facebook', 'internet/github'])
    assert read(db) == (
        'internet:\n'
        '  github:\n'
        '    password: fb\n'
        '    username: sakis\n'
    )


def test_get_keywords():
    # The `keywords` field is empty
    entry = {'username': 'takis', 'password': 'pass'}
    keywords = passata.get_keywords(entry)
    assert keywords == []

    # The `keywords` field contains a string
    entry = {'username': 'takis', 'password': 'pass',
             'keywords': 'Keyword'}
    keywords = passata.get_keywords(entry)
    assert keywords == ['keyword']

    # The `keywords` field contains a list of strings
    entry = {'username': 'takis', 'password': 'pass',
             'keywords': ['Google', 'YouTube', 'Gmail']}
    keywords = passata.get_keywords(entry)
    assert keywords == ['google', 'youtube', 'gmail']


def test_get_autotype(monkeypatch):
    # <autotype> field in entry
    entry = {'username': 'takis', 'password': 'pass',
             'autotype': '<password> !5 Return'}
    autotype = passata.get_autotype(entry)
    assert autotype == ['<password>', '!5', 'Return']

    # <username> and <password> fields in entry
    entry = {'username': 'takis', 'password': 'pass'}
    autotype = passata.get_autotype(entry)
    assert autotype == ['<username>', 'Tab', '<password>', 'Return']

    # <password> field in entry
    entry = {'name': 'takis', 'password': 'pass'}
    autotype = passata.get_autotype(entry)
    assert autotype == ['<password>', 'Return']

    # No known fields in entry
    # Suppress notification
    monkeypatch.setattr(passata, 'call', lambda command: None)
    entry = {'name': 'takis', 'pass': 'pass'}
    with pytest.raises(SystemExit):
        passata.get_autotype(entry)


def test_autotype(monkeypatch, db):
    monkeypatch.setattr(passata, 'active_window', lambda: (0, window_title))
    monkeypatch.setattr(passata, 'call', lambda command: print(command))

    window_title = 'GitHub: The world\'s leading blah blah blah'
    result = run(['autotype'])
    assert result.exception is None
    assert result.output == (
        "['xdotool', 'type', '--clearmodifiers', 'takis']\n"
        "['xdotool', 'key', 'Tab']\n"
        "['xdotool', 'type', '--clearmodifiers', 'gh']\n"
        "['xdotool', 'key', 'Return']\n"
    )


def test_autotype_no_username(monkeypatch, db):
    monkeypatch.setattr(passata, 'active_window', lambda: (0, window_title))
    monkeypatch.setattr(passata, 'call', lambda command: print(command))

    run(['insert', 'autotype/test1', '--password=pass1'])

    window_title = 'test1'
    result = run(['autotype'])
    assert result.exception is None
    assert result.output == (
        "['xdotool', 'type', '--clearmodifiers', 'pass1']\n"
        "['xdotool', 'key', 'Return']\n"
    )


def test_autotype_keywords_simple(monkeypatch, db):
    monkeypatch.setattr(passata, 'active_window', lambda: (0, window_title))
    monkeypatch.setattr(passata, 'call', lambda command: print(command))
    monkeypatch.setattr(click, 'edit', lambda x, editor, extension: updated)

    # Add a new entry with a single string in keywords
    updated = (
        'password: pass2\n'
        'keywords: the keyword\n'
    )
    run(['edit', 'autotype/test2'])

    window_title = 'A website with the keyword in its title'
    result = run(['autotype'])
    assert result.exception is None
    assert result.output == (
        "['xdotool', 'type', '--clearmodifiers', 'pass2']\n"
        "['xdotool', 'key', 'Return']\n"
    )


def test_autotype_keywords_complex(monkeypatch, db):
    monkeypatch.setattr(passata, 'active_window', lambda: (0, window_title))
    monkeypatch.setattr(passata, 'call', lambda command: print(command))
    monkeypatch.setattr(click, 'edit', lambda x, editor, extension: updated)

    # Add a new entry with an autotype field and a list of
    # strings in keywords that conflict with another entry.
    updated = (
        'username: user3\n'
        'password: pass3\n'
        'keywords:\n'
        '- github\n'
        '- yoyoyo\n'
        'autotype: <username> Return !1.5 <password> Return\n'
    )
    run(['edit', 'autotype/test3'])

    def fake_out(command, input):
        print('Calling', command)
        print('With input:')
        print(input)
        print()
        return 'autotype/test3'

    # Patch user interaction with dmenu to choose the new entry
    # and sleeping to just print for how long it would sleep.
    monkeypatch.setattr(passata, 'out', fake_out)
    monkeypatch.setattr('time.sleep',
                        lambda duration: print("Sleeping for", duration))

    window_title = 'GitHub'
    result = run(['autotype'])
    assert result.exception is None
    assert result.output == (
        "Calling ['dmenu']\n"
        "With input:\n"
        "autotype/test3\n"
        "internet/github\n"
        "\n"
        "['xdotool', 'type', '--clearmodifiers', 'user3']\n"
        "['xdotool', 'key', 'Return']\n"
        "Sleeping for 1.5\n"
        "['xdotool', 'type', '--clearmodifiers', 'pass3']\n"
        "['xdotool', 'key', 'Return']\n"
    )


def test_autotype_invalid(monkeypatch, db):
    monkeypatch.setattr(passata, 'active_window', lambda: (0, window_title))
    monkeypatch.setattr(click, 'edit', lambda x, editor, extension: updated)
    # Suppress notification
    monkeypatch.setattr(passata, 'call', lambda command: None)

    updated = (
        'password: pass4\n'
        'autotype: <username> Tab <password> Return\n'
    )
    run(['edit', 'autotype/test4'])

    window_title = 'test4'
    result = run(['autotype'])
    assert repr(result.exception) == 'SystemExit(1,)'
