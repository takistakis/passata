# passata

A simple password manager, inspired by [pass].

Supports a subset of pass's commands and options and unlike pass, all
passwords are stored in a single (gpg encrypted) file. It also has the
[keepassx]-like ability to automatically type passwords based on the
active window's title.

## Installation

Requirements:

- Python libraries: click, PyYAML
- Software: gpg, xdotool, dmenu, libnotify, xclip

For example for Arch Linux run:

`# pacman -S python-click python-yaml gnupg xdotool dmenu libnotify
xclip`

Install passata itself using `setup.py`. Note that doing so might make
startup too slow and cause a noticeable latency on autotyping. You may
want to just put `passata.py` to `$PATH` instead.

If you want to use zsh completion, you can copy `_passata` to a
directory in `$fpath`. `/usr/local/share/zsh/site-functions/` will
probably do.

## Usage

```
$ passata --help
Usage: passata [OPTIONS] COMMAND [ARGS]...

  A simple password manager, inspired by pass.

Options:
  --config PATH  Path of the configuration file.
  --version      Show the version and exit.
  --help         Show this message and exit.

Commands:
  autotype  Type login credentials.
  edit      Edit entry, group or the whole database.
  generate  Generate a random password.
  init      Initialize password database.
  insert    Insert a new password.
  ls        List entries in a tree-like format.
  mv        Move or rename entries.
  rm        Remove entries or groups.
  show      Decrypt and print entry.
```

See `passata <command> --help` for more info on a specific command.

## Autotype

By running `passata autotype`, passata tries to find the entry that
matches the active window's title, or prompt the user using dmenu if
there are more than one matches or no matches at all. Then types the
sequence that is specified in the `autotype` field of the entry.

This is supposed to be used by adding a keybinding for `passata
autotype` to your window manager's configuration.

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

## License

Licensed under GPLv3 or any later version.

[pass]: https://www.passwordstore.org/
[keepassx]: https://www.keepassx.org/
[pass-autotype]: https://github.com/wosc/pass-autotype
