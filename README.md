# passata

A simple password manager, inspired by [pass] for Linux and macOS.

Supports a subset of pass's commands and options and unlike pass, all
passwords are stored in a single (gpg encrypted) file. It also has the
[keepassx]-like ability to automatically type passwords based on the
active window's title. Autotyping currently only works on Linux.

## Installation

Requirements:

- Python 3.10 or newer
- Python libraries: click, PyYAML, watchdog
- Software: gpg, xdotool, dmenu, libnotify, xsel

For example for Arch Linux run:

```bash
pacman -S python-click python-yaml python-watchdog gnupg xdotool dmenu libnotify xsel
```

On macOS:

```bash
pip3 install --break-system-packages --upgrade --user click pyyaml watchdog
```

Install passata itself by running `sudo make install`, which also
installs the wordlists and the zsh completion script.

## Zsh completion

On macOS, the zsh completion of the passata entries, doesn't work with
the default pinentry program. To fix this you can install pinentry-mac
with `brew install pinentry-mac` and add the following to
`.gnupg/gpg-agent.conf`:

    pinentry-program /opt/homebrew/bin/pinentry-mac

Then restart the gpg-agent with `gpgconf --kill gpg-agent`.

## Usage

    $ passata --help
    Usage: passata [OPTIONS] COMMAND [ARGS]...

      A simple password manager, inspired by pass.

    Options:
      --config FILE         Path of the configuration file.
      --color / --no-color  Colorize the output.
      --version             Show the version and exit.
      -h, --help            Show this message and exit.

    Commands:
      autotype  Type login credentials.
      config    Edit the configuration file.
      edit      Edit entry, group or the whole database.
      find      List matching entries in a tree-like format.
      generate  Generate a random password.
      init      Initialize password database.
      insert    Insert a new password.
      ls        List entries in the database or a group.
      mv        Move or rename entries.
      rm        Remove entries or groups.
      show      Show entry, group or the whole database.
      tree      List entries in a tree-like format.

See `passata <command> --help` for more info on a specific command.

Run `passata init` first: it asks for a GnuPG ID and a database path
and writes the configuration file.

## Password generation

`passata generate [NAME]` creates a random password, copies it to the
clipboard (cleared after `--timeout` seconds) and, if NAME is given,
stores it in the database keeping the old password in `old_password`.

- `-l/--length`: number of characters or words (default 20).
- `-e/--entropy`: compute the length from the given bits of entropy
  (takes precedence over `--length`).
- `-s/--charset`: one of `letters`, `digits`, `alnum` or `full`
  (default).
- `-w/--wordlist`: generate a space separated passphrase from a
  wordlist, given either as a path or as the name of one of the
  installed wordlists (`bip39`, `eff_large_wordlist`, `markov`).

## Configuration

The configuration file is `~/.passata/config.yml`, and can be changed
with `--config` or the `PASSATA_CONFIG_PATH` environment variable. Use
`passata config` to edit it. Top level keys are global (`database`,
`gpg_id`, `color`), while a key that maps to a dict overrides the
default values of the options of the command with that name:

    database: ~/.passata.gpg
    gpg_id: user@example.com
    color: true
    generate:
      length: 30
      wordlist: eff_large_wordlist

If `~/.passata/hooks/pre-read` or `~/.passata/hooks/post-write` exist
and are executable, they are run before reading and after writing the
database respectively. They can be used for syncing the database.

## Autotype (Linux only)

By running `passata autotype`, passata tries to find the entry that
matches the active window's title. Specifically it looks for entries
whose name or any string in the `keywords` field, is included in the
title (case insensitive). If there are zero or more than one such
entries, the user is prompted to choose the right one using dmenu (or
any other menu command given with `--menu`). Finally the sequence that
is specified in the `autotype` field of the chosen entry is typed using
xdotool.

This is supposed to be used by adding a keybinding for `passata
autotype` to your window manager's configuration.

The `keywords` field can contain a string or list of strings.

The `autotype` field supports the following items:

- `<field>`: Types the contents of the given field of the entry (e.g.
  `<username>`).
- `Key`: Sends the specified keystroke (e.g. `Tab`, `Return`). See `man
  xdotool` for more information.
- `!time`: Sleeps for the given time (e.g. `!0.5`). Can be used to wait
  for the next page to load for services like gmail, where the username
  and password forms are on different pages.

The default autotype field is `<username> Tab <password> Return` if
there is both a `<username>` and a `<password>` field, or `<password>
Return` if there is only a `<password>`.

This feature is based on [pass-autotype], which I recommend if you want
something similar and prefer pass.

### Example

An entry for a google account could look like that:

    $ passata show internet/google
    username: user
    password: pass
    autotype: <username> Return !1.5 <password> Return
    keywords:
    - youtube
    - gmail

## License

Licensed under GPLv3 or any later version.

[pass]: https://www.passwordstore.org/
[keepassx]: https://www.keepassx.org/
[pass-autotype]: https://github.com/wosc/pass-autotype
