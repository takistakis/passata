import click
import pytest
from click.testing import CliRunner

import passata


@pytest.fixture
def db(monkeypatch):
    db = {'internet': {'facebook': {'username': 'sakis',
                                    'password': 'fb'},
                       'github': {'username': 'takis',
                                  'password': 'gh'}}}
    monkeypatch.setattr(passata, 'read_db', lambda: db)
    monkeypatch.setattr(passata, 'write_db', lambda db: None)
    monkeypatch.setattr(passata, 'read_config', lambda:
                        {'database': 'db', 'gpg_id': 'id'})
    yield db


def run(args):
    runner = CliRunner()
    return runner.invoke(passata.cli, args)


def clipboard():
    command = ['xclip', '-o', '-selection', 'clipboard']
    return passata.out(command)


def test_init(tmpdir):
    tempdir = tmpdir.mkdir('passata')
    confpath = tempdir.join('config.yml')
    dbpath = tempdir.join('passata.db')
    email = 'mail@mail.com'
    run(['--config=%s' % confpath, 'init',
         '--gpg-id=%s' % email, '--path=%s' % dbpath])
    contents = confpath.read()
    assert 'database: %s' % dbpath in contents
    assert 'gpg_id: %s' % email in contents


def test_ls(db):
    # List all
    result = run(['ls'])
    assert result.output == ('internet\n'
                             '├── facebook\n'
                             '└── github\n')

    # List group
    result = run(['ls', 'internet'])
    assert result.output == ('facebook\n'
                             'github\n')

    # --no-tree
    result = run(['ls', '--no-tree'])
    assert result.output == ('internet/facebook\n'
                             'internet/github\n')

    # Nonexistent group
    result = run(['ls', 'nonexistent'])
    assert repr(result.exception) == 'SystemExit(1,)'


def test_show(db):
    # Normal show
    result = run(['show', 'internet/github'])
    assert result.output == ('password: gh\n'
                             'username: takis\n')

    # Show nonexistent entry
    result = run(['show', 'internet/nonexistent'])
    assert repr(result.exception) == 'SystemExit(1,)'

    # Show entry three levels deep
    result = run(['show', 'one/two/three'])
    assert repr(result.exception) == 'SystemExit(1,)'

    # Clipboard
    result = run(['show', 'internet/github', '--clipboard'])
    assert result.output == ''
    assert clipboard() == 'gh'
    with pytest.raises(SystemExit):
        clipboard()

    # Try to put to clipboard a whole group
    result = run(['show', 'internet', '--clipboard'])
    assert repr(result.exception) == 'SystemExit(1,)'

    # Show group
    expected = ('facebook:\n'
                '  password: fb\n'
                '  username: sakis\n'
                'github:\n'
                '  password: gh\n'
                '  username: takis\n')
    result = run(['show', 'internet'])
    assert result.output == expected

    # Show group with trailing slash
    result = run(['show', 'internet/'])
    assert result.output == expected


def test_do_insert(monkeypatch, db):
    monkeypatch.setattr(click, 'confirm', lambda m: confirm)

    # Try to insert group
    with pytest.raises(SystemExit):
        passata.do_insert('group', force=True, password='...')

    # Insert entry
    passata.do_insert('group/test', force=True, password='one')
    assert db['group']['test']['password'] == 'one'

    # Force update
    passata.do_insert('group/test', force=True, password='two')
    assert db['group']['test']['password'] == 'two'
    assert db['group']['test']['password_old'] == 'one'

    # Confirm update
    confirm = True
    passata.do_insert('group/test', force=False, password='three')
    assert db['group']['test']['password'] == 'three'
    assert db['group']['test']['password_old'] == 'two'

    # Do not confirm update
    confirm = False
    with pytest.raises(SystemExit):
        passata.do_insert('group/test', force=False, password='four')


def test_insert(monkeypatch, db):
    run(['insert', 'group/test', '--force', '--password=password'])
    assert db['group']['test']['password'] == 'password'


def test_generate(monkeypatch, db):
    monkeypatch.setattr(passata, 'generate_password', lambda l, s: l * 'x')

    # Too short length
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
    with pytest.raises(SystemExit):
        clipboard()


def test_edit_entry(monkeypatch, db):
    monkeypatch.setattr(click, 'edit', lambda x, editor, extension: updated)
    monkeypatch.setattr(click, 'confirm', lambda m: confirm)

    updated = ('username: takis\n'
               'password: secret\n')
    run(['edit', 'internet/reddit'])
    assert db['internet']['reddit']['password'] == 'secret'

    updated = ''
    confirm = True
    run(['edit', 'internet/reddit'])
    assert 'reddit' not in db['internet']

    updated = ('username: sakis\n'
               'password: yolo\n')
    run(['edit', 'mail/gmail'])
    assert db['mail']['gmail']['password'] == 'yolo'

    updated = ''
    confirm = False
    run(['edit', 'mail/gmail'])
    assert db['mail']['gmail']['password'] == 'yolo'

    updated = ''
    confirm = True
    run(['edit', 'mail/gmail'])
    assert 'mail' not in db

    # Cover the possibility of leaving empty an already empty entry
    updated = ''
    confirm = True
    run(['edit', 'asdf/asdf'])
    assert 'asdf' not in db


def test_edit_group(monkeypatch, db):
    monkeypatch.setattr(click, 'edit', lambda x, editor, extension: updated)
    monkeypatch.setattr(click, 'confirm', lambda m: confirm)

    updated = ''
    confirm = False
    run(['edit', 'internet'])
    assert 'internet' in db

    updated = ''
    confirm = True
    run(['edit', 'internet'])
    assert 'internet' not in db

    # Cover the possibility of leaving empty an already empty group
    updated = ''
    confirm = True
    run(['edit', 'asdf'])
    assert 'asdf' not in db

    updated = ('facebook:\n'
               '  username: takis\n'
               '  password: secret\n')
    run(['edit', 'internet'])
    assert db == {'internet': {'facebook': {'username': 'takis',
                                            'password': 'secret'}}}


def test_edit_database(monkeypatch, db):
    monkeypatch.setattr(click, 'edit', lambda x, editor, extension: updated)
    monkeypatch.setattr(click, 'confirm', lambda m: confirm)

    updated = ('internet:\n'
               '  facebook:\n'
               '    username: sakis\n'
               '    password: fb\n')

    confirm = True
    run(['edit'])
    assert db == {'internet': {'facebook': {'username': 'sakis',
                                            'password': 'fb'}}}

    copy = db.copy()
    updated = ''
    confirm = False
    run(['edit'])
    assert db == copy

    updated = ''
    confirm = True
    run(['edit'])
    assert db == {}


def test_rm_entry(monkeypatch, db):
    # Normal removal
    run(['rm', '--force', 'internet/facebook'])
    assert db == {'internet': {'github': {'username': 'takis',
                                          'password': 'gh'}}}

    # Remove nonexistent entry
    result = run(['rm', 'internet/nonexistent'])
    assert repr(result.exception) == 'SystemExit(1,)'

    # Do not confirm removal
    monkeypatch.setattr(click, 'confirm', lambda m: False)
    run(['rm', 'internet/github'])
    assert 'github' in db['internet']

    # Remove last entry
    run(['rm', '--force', 'internet/github'])
    assert db == {}


def test_rm_entries(db):
    run(['rm', '--force', 'internet/facebook', 'internet/github'])
    assert db == {}

    result = run(['rm', '--force', 'asdf/asdf', 'asdf/asdf2'])
    assert repr(result.exception) == 'SystemExit(1,)'


def test_rm_group(db):
    result = run(['rm', '--force', 'asdf'])
    assert repr(result.exception) == 'SystemExit(1,)'

    run(['rm', '--force', 'internet'])
    assert db == {}


def test_mv_entry_to_entry(db):
    run(['mv', 'internet/facebook', 'internet/fb'])
    assert db == {'internet': {'fb': {'username': 'sakis',
                                      'password': 'fb'},
                               'github': {'username': 'takis',
                                          'password': 'gh'}}}


def test_mv_entry_to_group(db):
    run(['mv', 'internet/facebook', 'new'])
    assert db == {'new': {'facebook': {'username': 'sakis',
                                       'password': 'fb'}},
                  'internet': {'github': {'username': 'takis',
                                          'password': 'gh'}}}


def test_mv_entries_to_entry(db):
    result = run(['mv', 'internet/facebook', 'internet/github', 'new/new'])
    assert repr(result.exception) == 'SystemExit(1,)'


def test_mv_entries_to_group(db):
    run(['mv', 'internet/facebook', 'internet/github', 'new'])
    assert db == {'new': {'facebook': {'username': 'sakis',
                                       'password': 'fb'},
                  'github': {'username': 'takis',
                             'password': 'gh'}}}


def test_mv_nonexistent_entry(db):
    result = run(['mv', 'internet/nonexistent', 'group'])
    assert repr(result.exception) == 'SystemExit(1,)'


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
