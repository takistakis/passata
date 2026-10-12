# Autotype on macOS

This guide assumes passata is already installed and configured. macOS
autotype uses built-in System Events; no xdotool or dmenu is needed.

## 1. Create a keyboard shortcut

Autotype targets the window active when the command starts. Running
`passata autotype` directly in Terminal targets Terminal, not your browser.
Use a background shortcut instead.

1. Open **Automator** and create a **Quick Action**.
2. Set **Workflow receives** to **no input** in **any application**.
3. Add **Run Shell Script**, selecting `/bin/zsh`, and enter:

```sh
export PATH="/opt/homebrew/bin:/usr/local/bin:/usr/bin:/bin"
exec /absolute/path/to/passata autotype
```

Use `command -v passata` in Terminal to find the actual executable path.
If your installation requires a virtual-environment interpreter, use
that interpreter explicitly, for example:

```sh
export PATH="/opt/homebrew/bin:/usr/local/bin:/usr/bin:/bin"
exec "$HOME/.venvs/passata/bin/python" /usr/local/bin/passata autotype
```

Save the action as **Passata Autotype**, then assign an unused shortcut
under **System Settings > Keyboard > Keyboard Shortcuts > Services**.
Other background command launchers can run the same script, provided
they do not activate their own window.

If needed, specify your configuration before the command:
`passata --config /path/to/config.yml autotype`.

## 2. Grant macOS permissions

Invoke the **saved keyboard shortcut from the target app**, not just the
Run button inside Automator. macOS permissions depend on how the action
is launched; authorizing Terminal or Automator does not necessarily
authorize the saved Quick Action.

Under **System Settings > Privacy & Security**, grant both permissions:

1. **Device Control and Data Access** (macOS 27), or **Accessibility**
   (macOS 26 and earlier): enable the app or workflow runner responsible for
   the shortcut. For an Automator Quick Action this is often
   **WorkflowServiceRunner**; when testing with Automator's Run button it
   may be **Automator** instead. Other launchers need their own permission.
   Use the name shown in macOS's prompt or permission list; names can vary
   by macOS version and launch method.
2. **Automation:** under that app or runner, enable **System Events**.
   This is separate from Accessibility access.

On macOS 27, the full path is **System Settings > Privacy & Security >
Device Control and Data Access**. Errors may still call this permission
"Accessibility" or "assistive access". This is not the top-level
Accessibility settings pane. See also
[Microsoft's macOS 27 permission guidance](https://learn.microsoft.com/en-us/purview/endpoint-dlp-macos-27-changes#permission-changes-in-macos-27).

The error **`osascript is not allowed assistive access. (-25211)`** means
Accessibility access is missing or stale. It does **not** mean you
should automatically add `/usr/bin/osascript` or grant access to the
target browser. macOS can name the child process in the error while
assigning permission to its launcher.

If no permission prompt appears, open Device Control and Data Access
(Accessibility on older macOS versions) manually. A failed invocation
usually adds the runner to the list **switched off** without prompting.
Look for **WorkflowServiceRunner** and turn its toggle on. Granting the
target app, such as iTerm or your browser, does not help.

macOS checks WorkflowServiceRunner by its bundle identifier,
`com.apple.automator.xpc.workflowServiceRunner`. If you added the runner
manually but the error persists, the entry may not match that
identifier. Remove only that entry with **−**, invoke the shortcut once
so macOS adds it again, then switch it on.

If the runner is absent even after invoking the shortcut, use **+** to
add it. For WorkflowServiceRunner on macOS 27, press **Command-Shift-G**
in the file picker and paste this full executable path:

```text
/System/Library/Frameworks/AppKit.framework/Versions/C/XPCServices/WorkflowServiceRunner.xpc/Contents/MacOS/WorkflowServiceRunner
```

Select the executable and click **Open**, then enable its toggle.
This runner is inside an XPC service, not
`/System/Library/CoreServices/WorkflowServiceRunner.app`.
Its location may differ on other macOS versions.
For Automator, select Automator.app.
Only authorize the runner you actually use.

After changing permissions, quit and reopen the launcher. For a Quick
Action, quit every **WorkflowServiceRunner** process in Activity Monitor
so the next invocation starts it again. Then refocus the target app and
invoke the shortcut again; it may now request Automation access. If an
existing Accessibility entry remains ineffective, remove and re-add that
specific runner, then restart it. Do not reset all macOS privacy permissions.

To see which app macOS checked, run this right after a failed attempt:

```sh
log show --last 2m --style compact --predicate \
  'process == "tccd" AND eventMessage CONTAINS "AUTHREQ"' |
  grep -A3 kTCCServiceAccessibility | grep -E 'SUBJECT|RESULT'
```

`subject=` names the app that needs permission. Match each result to its
subject by `msgID`. `authValue=0` means access was denied; `authValue=2`
means access was allowed. Ignore unrelated subjects, such as other
utilities that check their own permission.

An Automation error such as **`Not authorized to send Apple events to
System Events. (-1743)`** needs the Automation permission above, not just
Accessibility. If a managed Mac prevents permission changes, contact
its administrator; passata cannot bypass these checks.

A background action also needs graphical GnuPG pinentry if your key's
passphrase is not cached. If decryption cannot prompt, follow the
[pinentry-mac setup in the README](README.md#zsh-completion).

## 3. Test with dummy credentials

Create an entry with `passata insert autotype-test`, then edit it with
`passata edit autotype-test`:

```yaml
username: demo-user
password: demo-password
keywords:
  - passata-autotype-test
autotype: <username> Tab <password>
```

Save a TextEdit document as `passata-autotype-test.txt`, focus it, and
invoke the shortcut. Release the shortcut's keys immediately. The dummy
username and password should appear separated by a tab. The sequence
omits `Return` to avoid submitting anything.

Then test a disposable login form in your intended browser, adjusting
`keywords` to match its window title. Focus the username field before
invoking the shortcut.

Passata matches entry names and keywords against the window title,
case-insensitively. One match is selected automatically; otherwise a
native picker appears. Cancelling types nothing. Remove any existing
`autotype.menu: dmenu` configuration to use the native picker.

## Sequences and timing

The default sequence is `<username> Tab <password> Return`, or
`<password> Return` for password-only entries. Override it in the entry's
`autotype` field or with `--sequence`.

| Item | Action |
|---|---|
| `<field>` | Type the field's contents, preserving spaces. |
| `Tab`, `Return`, `Enter` | Tab, ordinary Return, keypad Enter. |
| `Escape`, `BackSpace`, `Delete`, `space` | Escape, backward delete, forward delete, space. |
| `Left`, `Right`, `Up`, `Down` | Arrow keys. |
| `Home`, `End`, `Page_Up`, `Page_Down` | Navigation keys. |
| `a`, `+` | Send a single character. |
| `shift+Tab`, `cmd+a`, `cmd++` | Send a key with modifiers. |
| `!0.5` | Pause for 0.5 seconds. |

Modifiers are case-insensitive: `shift`, `ctrl`/`control`,
`alt`/`option`, `cmd`/`command`/`super`. Named keys are case-sensitive.
Unlisted multi-character keys, including function keys, are unsupported.

The default character delay is 50 ms. Use `--delay 100` for slower
applications, or set a default in passata's configuration:

```yaml
autotype:
  delay: 100
```

To pause before typing, use an entry sequence such as:

```yaml
autotype: "!0.5 <username> Tab <password>"
```

## Troubleshooting and safety

| Problem | Action |
|---|---|
| `not allowed assistive access` / `-25211` | Follow section 2: switch on the runner (usually WorkflowServiceRunner, possibly already listed but off), then quit it. Terminal or target-app permission is not sufficient. |
| `Not authorized to send Apple events` / `-1743` | Enable System Events under the runner's Automation permissions; see section 2. |
| `gpg` not found or Python imports fail | Set the workflow's PATH and use the interpreter from your working installation. |
| GnuPG cannot prompt | Configure graphical pinentry; see the README link above. |
| Credentials appear in Terminal | Use the background shortcut, not an interactive Terminal command. |
| `Window has changed` | Keep the original window focused. After pinentry it must regain focus; page-title changes also cause an abort. |
| `No accessible active window` | Check permissions and focus a normal document/browser window. |
| `dmenu` not found | Remove `--menu dmenu` or the corresponding configuration setting. |
| Missing or incorrect characters | Release shortcut modifiers, increase the delay, and test your keyboard layout with dummy data. |

Do not switch windows or interact while typing. Passata checks the
application PID and window title before each character, but cannot
detect a different field or two same-title windows in the same app.
Window-title matching does not verify a website's identity.

Autotype does not use the clipboard or put credentials in command-line
arguments. Application input handling, non-ASCII characters, and protected
prompts may still affect results. Verify exact output with dummy
credentials before using real passwords; never disable the focus checks
to work around an error.
