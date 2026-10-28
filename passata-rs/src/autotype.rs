// Copyright 2026 Panagiotis Ktistakis <panktist@gmail.com>
//
// This file is part of passata-rs.
//
// passata-rs is free software: you can redistribute it and/or modify
// it under the terms of the GNU General Public License as published by
// the Free Software Foundation, either version 3 of the License, or
// (at your option) any later version.
//
// passata-rs is distributed in the hope that it will be useful,
// but WITHOUT ANY WARRANTY; without even the implied warranty of
// MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
// GNU General Public License for more details.
//
// You should have received a copy of the GNU General Public License
// along with passata-rs.  If not, see <http://www.gnu.org/licenses/>.

use std::io::Write;
use std::process::{Command, Stdio};
use std::time::Duration;

use clap::ArgMatches;
use yaml_rust::Yaml;

use crate::database::{Database, is_entry};
use crate::utils::{config_setting, scalar_string};

/// One step of an autotype sequence, resolved before any input is simulated.
#[derive(Debug, PartialEq)]
enum Action {
    Text(String),
    Key(String),
    Sleep(Duration),
}

/// Mirror Python truthiness so empty or zero-valued fields count as missing.
fn is_truthy(value: &Yaml) -> bool {
    match value {
        Yaml::Null | Yaml::BadValue => false,
        Yaml::Boolean(value) => *value,
        Yaml::Integer(value) => *value != 0,
        Yaml::Real(value) => value.parse::<f64>().map_or(true, |value| value != 0.0),
        Yaml::String(value) => !value.is_empty(),
        Yaml::Array(values) => !values.is_empty(),
        Yaml::Hash(map) => !map.is_empty(),
        Yaml::Alias(_) => true,
    }
}

/// Return the entry's keywords as lowercase strings.
fn keywords(entry: &Yaml) -> Vec<String> {
    match &entry["keywords"] {
        Yaml::Null | Yaml::BadValue => Vec::new(),
        Yaml::Array(words) => words.iter().map(|w| scalar_string(w).to_lowercase()).collect(),
        word => vec![scalar_string(word).to_lowercase()],
    }
}

/// Return all entry paths and those whose name or keywords appear in the window title.
fn match_entries(db: &Database, title: &str) -> (Vec<String>, Vec<String>) {
    let title = title.to_lowercase();
    let mut names = Vec::new();
    let mut matches = Vec::new();
    for (path, entry) in db.entries() {
        let entryname = path.rsplit('/').next().unwrap_or_default().to_lowercase();
        if std::iter::once(entryname)
            .chain(keywords(entry))
            .any(|keyword| title.contains(&keyword))
        {
            matches.push(path.clone());
        }
        names.push(path);
    }
    (names, matches)
}

/// Return the items to type, defaulting to username/password based on the entry's fields.
fn sequence_keys(entry: &Yaml) -> Result<Vec<String>, String> {
    let sequence = match &entry["autotype"] {
        Yaml::Null | Yaml::BadValue => {
            if is_truthy(&entry["username"]) && is_truthy(&entry["password"]) {
                String::from("<username> Tab <password> Return")
            } else if is_truthy(&entry["password"]) {
                String::from("<password> Return")
            } else {
                return Err(String::from("Don't know what to type :("));
            }
        }
        Yaml::String(sequence) => sequence.clone(),
        _ => return Err(String::from("Invalid autotype field")),
    };
    Ok(sequence.split_whitespace().map(str::to_owned).collect())
}

/// Resolve `<field>` values and `!seconds` pauses; anything else is a key.
fn parse_actions(keys: &[String], entry: &Yaml) -> Result<Vec<Action>, String> {
    keys.iter()
        .map(|key| {
            if key.len() >= 2 && key.starts_with('<') && key.ends_with('>') {
                let field = &key[1..key.len() - 1];
                let value = &entry[field];
                if !is_truthy(value) {
                    return Err(format!("{} not found", field));
                }
                Ok(Action::Text(scalar_string(value)))
            } else if let Some(seconds) = key.strip_prefix('!') {
                seconds
                    .parse::<f64>()
                    .ok()
                    .and_then(|seconds| Duration::try_from_secs_f64(seconds).ok())
                    .map(Action::Sleep)
                    .ok_or_else(|| format!("Invalid sleep duration: {}", key))
            } else {
                Ok(Action::Key(key.clone()))
            }
        })
        .collect()
}

/// Determine the menu command from the CLI, then the configuration, defaulting to dmenu.
fn menu_command(
    args: &ArgMatches,
    config: Option<&Yaml>,
    root_config: &Yaml,
) -> Result<Vec<String>, String> {
    let command = match args.get_one::<String>("menu") {
        Some(menu) => shlex::split(menu),
        None => match config_setting(config, root_config, "menu") {
            None | Some(Yaml::Null) => Some(vec![String::from("dmenu")]),
            Some(Yaml::Array(items)) => Some(items.iter().map(scalar_string).collect()),
            Some(Yaml::String(menu)) => shlex::split(menu),
            Some(_) => None,
        },
    };
    command
        .filter(|command| !command.is_empty())
        .ok_or_else(|| String::from("Invalid menu command"))
}

/// Run a command with `input` on stdin and return its standard output.
fn run_menu(command: &[String], input: &str) -> Result<String, String> {
    let mut child = Command::new(&command[0])
        .args(&command[1..])
        .stdin(Stdio::piped())
        .stdout(Stdio::piped())
        .stderr(Stdio::piped())
        .spawn()
        .map_err(|_| format!("Executable '{}' not found", command[0]))?;
    let mut stdin = child.stdin.take().expect("piped stdin");
    // Ignore write errors (e.g. a menu that exits early); the exit status is what matters.
    let _ = stdin.write_all(input.as_bytes());
    drop(stdin);
    let output = child
        .wait_with_output()
        .map_err(|e| format!("Couldn't run '{}': {}", command[0], e))?;
    if !output.status.success() {
        let stderr = String::from_utf8_lossy(&output.stderr);
        let detail = if stderr.trim().is_empty() {
            String::new()
        } else {
            format!("\n{}", stderr.trim())
        };
        return Err(format!(
            "Command '{}' returned non-zero exit status {}.{}",
            command.join(" "),
            output.status.code().unwrap_or(-1),
            detail
        ));
    }
    Ok(String::from_utf8_lossy(&output.stdout).into_owned())
}

/// Pick the single matching entry or ask the menu, offering matches or else every entry.
fn choose_entry(
    names: &[String],
    matches: &[String],
    menu: &[String],
) -> Result<String, String> {
    if names.is_empty() {
        return Err(String::from("No entries to autotype"));
    }
    if let [only] = matches {
        return Ok(only.trim().to_owned());
    }
    let mut choices = if matches.is_empty() { names } else { matches }.to_vec();
    choices.sort();
    Ok(run_menu(menu, &choices.join("\n"))?.trim().to_owned())
}

/// Type the credentials of the entry that matches the active window.
pub fn autotype(
    db: &Database,
    args: &ArgMatches,
    config: Option<&Yaml>,
    root_config: &Yaml,
) -> Result<(), String> {
    let mut backend = backend::Backend::connect()?;
    let window = backend.active_window()?;
    let (names, matches) = match_entries(db, &window.name);
    let menu = menu_command(args, config, root_config)?;
    let choice = choose_entry(&names, &matches, &menu)?;
    let entry = db
        .get_optional(Some(&choice))
        .ok()
        .flatten()
        .filter(|entry| is_entry(entry))
        .ok_or_else(|| String::from("No valid entry selected"))?;
    let keys = match args.get_one::<String>("sequence") {
        Some(sequence) if !sequence.trim().is_empty() => {
            sequence.split_whitespace().map(str::to_owned).collect()
        }
        _ => sequence_keys(entry)?,
    };
    let actions = parse_actions(&keys, entry)?;
    // Validate every key before typing anything, so a typo doesn't leave a half-typed login.
    for action in &actions {
        if let Action::Key(key) = action {
            backend.check_key(key)?;
        }
    }
    let delay = Duration::from_millis(*args.get_one::<u64>("delay").unwrap_or(&50));
    for action in &actions {
        if backend.active_window()? != window {
            return Err(String::from("Window has changed"));
        }
        match action {
            Action::Text(text) => backend.type_text(text, delay)?,
            Action::Key(key) => backend.press_key(key)?,
            Action::Sleep(duration) => std::thread::sleep(*duration),
        }
    }
    Ok(())
}

#[cfg(target_os = "linux")]
mod backend {
    use std::ffi::{CString, c_char, c_int, c_void};
    use std::sync::OnceLock;
    use std::time::Duration;

    use enigo::{Direction, Enigo, Key, Keyboard, Settings};
    use x11rb::connection::Connection;
    use x11rb::protocol::xproto::{Atom, AtomEnum, ConnectionExt, KeyButMask, Window as XWindow};
    use x11rb::rust_connection::RustConnection;

    #[derive(Debug, PartialEq)]
    pub struct Window {
        id: XWindow,
        pub name: String,
    }

    /// X11 window queries via x11rb and keyboard simulation via XTEST (enigo).
    pub struct Backend {
        connection: RustConnection,
        root: XWindow,
        net_active_window: Atom,
        net_wm_name: Atom,
        enigo: Option<Enigo>,
    }

    fn x11_error(error: impl std::fmt::Display) -> String {
        format!("X11 error: {}", error)
    }

    impl Backend {
        pub fn connect() -> Result<Self, String> {
            let (connection, screen) = x11rb::connect(None).map_err(|e| {
                format!("Couldn't connect to the X server (autotype requires X11): {}", e)
            })?;
            let root = connection.setup().roots[screen].root;
            let intern = |name: &[u8]| -> Result<Atom, String> {
                Ok(connection
                    .intern_atom(false, name)
                    .map_err(x11_error)?
                    .reply()
                    .map_err(x11_error)?
                    .atom)
            };
            let net_active_window = intern(b"_NET_ACTIVE_WINDOW")?;
            let net_wm_name = intern(b"_NET_WM_NAME")?;
            Ok(Self {
                connection,
                root,
                net_active_window,
                net_wm_name,
                enigo: None,
            })
        }

        fn property(&self, window: XWindow, property: Atom) -> Result<Vec<u8>, String> {
            Ok(self
                .connection
                .get_property(false, window, property, AtomEnum::ANY, 0, u32::MAX / 4)
                .map_err(x11_error)?
                .reply()
                .map_err(x11_error)?
                .value)
        }

        /// Get the active window's id and title, like `xdotool getactivewindow getwindowname`.
        pub fn active_window(&self) -> Result<Window, String> {
            let id = self
                .connection
                .get_property(false, self.root, self.net_active_window, AtomEnum::WINDOW, 0, 1)
                .map_err(x11_error)?
                .reply()
                .map_err(x11_error)?
                .value32()
                .and_then(|mut values| values.next())
                .filter(|&id| id != x11rb::NONE)
                .ok_or_else(|| String::from("Couldn't get the active window"))?;
            let mut name = self.property(id, self.net_wm_name)?;
            if name.is_empty() {
                name = self.property(id, AtomEnum::WM_NAME.into())?;
            }
            Ok(Window {
                id,
                name: String::from_utf8_lossy(&name).into_owned(),
            })
        }

        fn enigo(&mut self) -> Result<&mut Enigo, String> {
            if self.enigo.is_none() {
                let enigo = Enigo::new(&Settings::default())
                    .map_err(|e| format!("Couldn't initialize keyboard simulation: {}", e))?;
                self.enigo = Some(enigo);
            }
            Ok(self.enigo.as_mut().expect("initialized above"))
        }

        /// Release modifiers that are still held (e.g. from the hotkey that started autotype),
        /// like xdotool's `--clearmodifiers`.
        fn clear_modifiers(&mut self) -> Result<(), String> {
            let pressed = self
                .connection
                .query_keymap()
                .map_err(x11_error)?
                .reply()
                .map_err(x11_error)?
                .keys;
            let mut keycodes = self
                .connection
                .get_modifier_mapping()
                .map_err(x11_error)?
                .reply()
                .map_err(x11_error)?
                .keycodes;
            keycodes.retain(|&kc| kc != 0 && pressed[usize::from(kc / 8)] & (1 << (kc % 8)) != 0);
            keycodes.sort_unstable();
            keycodes.dedup();
            for keycode in keycodes {
                self.enigo()?
                    .raw(keycode.into(), Direction::Release)
                    .map_err(|e| format!("Couldn't release modifier: {}", e))?;
            }
            Ok(())
        }

        fn caps_lock_on(&self) -> Result<bool, String> {
            Ok(self
                .connection
                .query_pointer(self.root)
                .map_err(x11_error)?
                .reply()
                .map_err(x11_error)?
                .mask
                .contains(KeyButMask::LOCK))
        }

        fn toggle_caps_lock(&mut self) -> Result<(), String> {
            self.enigo()?
                .key(Key::CapsLock, Direction::Click)
                .map_err(|e| format!("Couldn't toggle Caps Lock: {}", e))
        }

        /// Type text one character at a time, waiting `delay` after each keystroke.
        pub fn type_text(&mut self, text: &str, delay: Duration) -> Result<(), String> {
            self.clear_modifiers()?;
            let caps_lock = self.caps_lock_on()?;
            if caps_lock {
                self.toggle_caps_lock()?;
            }
            let mut result = Ok(());
            for character in text.chars() {
                result = self
                    .enigo()?
                    .key(Key::Unicode(character), Direction::Click)
                    .map_err(|e| format!("Couldn't type text: {}", e));
                if result.is_err() {
                    break;
                }
                std::thread::sleep(delay);
            }
            if caps_lock {
                self.toggle_caps_lock()?;
            }
            result
        }

        pub fn check_key(&self, key: &str) -> Result<(), String> {
            parse_key(key).map(|_| ())
        }

        /// Press a key combination such as `Return` or `ctrl+alt+Delete`.
        pub fn press_key(&mut self, key: &str) -> Result<(), String> {
            let keysyms = parse_key(key)?;
            self.clear_modifiers()?;
            let enigo = self.enigo()?;
            let error = |e: enigo::InputError| format!("Couldn't press {}: {}", key, e);
            for &keysym in &keysyms {
                enigo.key(Key::Other(keysym), Direction::Press).map_err(error)?;
            }
            for &keysym in keysyms.iter().rev() {
                enigo.key(Key::Other(keysym), Direction::Release).map_err(error)?;
            }
            Ok(())
        }
    }

    type KeysymFromName = unsafe extern "C" fn(*const c_char, c_int) -> u32;
    const XKB_KEYSYM_CASE_INSENSITIVE: c_int = 1 << 0;

    /// Load `xkb_keysym_from_name` at runtime so building doesn't need libxkbcommon headers.
    fn keysym_from_name_fn() -> Option<KeysymFromName> {
        static FUNCTION: OnceLock<Option<KeysymFromName>> = OnceLock::new();
        *FUNCTION.get_or_init(|| unsafe {
            let handle = libc::dlopen(c"libxkbcommon.so.0".as_ptr(), libc::RTLD_NOW);
            if handle.is_null() {
                return None;
            }
            let symbol = libc::dlsym(handle, c"xkb_keysym_from_name".as_ptr());
            if symbol.is_null() {
                return None;
            }
            Some(std::mem::transmute::<*mut c_void, KeysymFromName>(symbol))
        })
    }

    /// Resolve an X keysym name (e.g. `Return`, `a`, `U+00E9`), falling back to a
    /// case-insensitive lookup.
    fn keysym(name: &str) -> Result<Option<u32>, String> {
        let from_name = keysym_from_name_fn()
            .ok_or_else(|| String::from("Couldn't load libxkbcommon.so.0"))?;
        let Ok(name) = CString::new(name) else {
            return Ok(None);
        };
        let keysym = unsafe { from_name(name.as_ptr(), 0) };
        let keysym = if keysym == 0 {
            unsafe { from_name(name.as_ptr(), XKB_KEYSYM_CASE_INSENSITIVE) }
        } else {
            keysym
        };
        Ok((keysym != 0).then_some(keysym))
    }

    /// Split an xdotool-style key combination and resolve each part to a keysym.
    pub(super) fn parse_key(key: &str) -> Result<Vec<u32>, String> {
        super::key_names(key)
            .ok_or_else(|| format!("Invalid key: {}", key))?
            .into_iter()
            .map(|name| keysym(name)?.ok_or_else(|| format!("Invalid key: {}", key)))
            .collect()
    }
}

/// Split `mod+mod+key` into keysym names, expanding xdotool's modifier aliases.
#[cfg_attr(not(target_os = "linux"), allow(dead_code))]
fn key_names(key: &str) -> Option<Vec<&str>> {
    let (modifiers, name) = match key.strip_suffix("++") {
        Some(modifiers) => (modifiers, "plus"),
        None if key == "+" => ("", "plus"),
        None => key.rsplit_once('+').unwrap_or(("", key)),
    };
    let mut names: Vec<&str> = if modifiers.is_empty() {
        Vec::new()
    } else {
        modifiers.split('+').collect()
    };
    names.push(name);
    if names.iter().any(|name| name.is_empty()) {
        return None;
    }
    for name in &mut names {
        *name = match name.to_lowercase().as_str() {
            "ctrl" | "control" => "Control_L",
            "alt" => "Alt_L",
            "shift" => "Shift_L",
            "super" => "Super_L",
            "meta" => "Meta_L",
            _ => name,
        };
    }
    Some(names)
}

#[cfg(not(target_os = "linux"))]
mod backend {
    use std::time::Duration;

    #[derive(Debug, PartialEq)]
    pub struct Window {
        pub name: String,
    }

    pub struct Backend;

    impl Backend {
        pub fn connect() -> Result<Self, String> {
            Err(String::from("autotype is currently only supported on Linux"))
        }

        pub fn active_window(&self) -> Result<Window, String> {
            unreachable!()
        }

        pub fn check_key(&self, _key: &str) -> Result<(), String> {
            unreachable!()
        }

        pub fn type_text(&mut self, _text: &str, _delay: Duration) -> Result<(), String> {
            unreachable!()
        }

        pub fn press_key(&mut self, _key: &str) -> Result<(), String> {
            unreachable!()
        }
    }
}

#[cfg(test)]
#[path = "../tests/unit/autotype.rs"]
mod tests;
