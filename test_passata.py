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
    return open(dbpath).read()


def run(args):
    runner = click.testing.CliRunner()
    return runner.invoke(passata.cli, args)


def clipboard():
    command = ['xclip', '-o', '-selection', 'clipboard']
    return passata.out(command)


def test_init(tmpdir, monkeypatch):
    monkeypatch.setattr(passata, 'encrypt', lambda x: x)
    monkeypatch.setattr(passata, 'decrypt', lambda x: open(x).read())

    confpath = tmpdir.join('config.yml')
    dbpath = tmpdir.join('passata.db')

    # Try to execute a command without having initialized passata
    result = run(['--config', confpath, 'ls'])
    assert repr(result.exception) == 'SystemExit(1,)'
    assert result.output == "Run `passata init` first\n"

    # Initialize
    result = run(['--config', confpath, 'ls'])
    email = 'mail@mail.com'
    run(['--config=%s' % confpath, 'init',
         '--gpg-id=%s' % email, '--path=%s' % dbpath])
    contents = confpath.read()
    assert 'database: %s' % dbpath in contents
    assert 'gpg_id: %s' % email in contents

    # Try again and now it should work
    result = run(['--config', confpath, 'ls'])
    assert result.output == ''

    # Try again after deleting the database and it should fail
    os.unlink(dbpath)
    result = run(['--config', confpath, 'ls'])
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

    # Try to put a whole group to clipboard
    result = run(['show', 'internet', '--clipboard'])
    assert repr(result.exception) == 'SystemExit(1,)'

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
        '    password_old: one\n'
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
        '    password_old: two\n'
    )

    # Do not confirm update
    confirm = False
    result = run(['insert', 'group', '--password=four'])
    assert repr(result.exception) == 'SystemExit(1,)'


def test_generate(monkeypatch, db):
    monkeypatch.setattr(passata, 'generate_password', lambda l, s: l * 'x')

    # Too short
    result = run(['generate', '--length=2'])
    assert result.exit_code == 2
    assert 'Error' in result.output

    result = run(['generate'])
    assert result.output == 'xxxxxxxxxxxxxxxxxxxx\n'

    result = run(['generate', 'asdf/test', '--length=5', '--force'])
    assert result.output == 'xxxxx\n'

    result = run(['generate', 'asdf/test', '--length=5', '--force',
                  '--clipboard'])
    assert result.output == ''
    assert clipboard() == 'xxxxx'
    assert clipboard() == 'xxxxx'
    # Should be gone after being pasted twice
    with pytest.raises(SystemExit):
        clipboard()


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
