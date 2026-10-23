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

use std::fs::File;
use std::io::{self, IsTerminal, Write};
use std::path::Path;

use yaml_rust::Yaml;

/// Create a new file readable and writable only by the current user, failing if it exists.
pub fn create_private_file(path: &Path) -> io::Result<File> {
    use std::os::unix::fs::OpenOptionsExt;

    std::fs::OpenOptions::new()
        .write(true)
        .create_new(true)
        .mode(0o600)
        .open(path)
}

/// Look up a setting in the command's configuration, falling back to the root configuration.
pub fn config_setting<'a>(config: Option<&'a Yaml>, root: &'a Yaml, key: &str) -> Option<&'a Yaml> {
    config
        .and_then(|config| crate::config_value(config, key))
        .or_else(|| crate::config_value(root, key))
}

/// Resolve a boolean flag that is enabled by either the CLI or the configuration.
pub fn flag_or_setting(
    args: &clap::ArgMatches,
    config: Option<&Yaml>,
    root: &Yaml,
    key: &str,
) -> bool {
    args.get_flag(key)
        || config_setting(config, root, key)
            .and_then(Yaml::as_bool)
            .unwrap_or(false)
}

/// Prompt for yes/no confirmation, defaulting to no or accepting immediately when forced.
pub fn confirm(message: &str, force: bool) -> Result<bool, String> {
    if force {
        return Ok(true);
    }
    loop {
        print!("{} [y/N]: ", message);
        io::stdout()
            .flush()
            .map_err(|e| format!("Failed to flush stdout: {}", e))?;
        let mut input = String::new();
        let bytes = io::stdin()
            .read_line(&mut input)
            .map_err(|e| format!("Failed to read from stdin: {}", e))?;
        if bytes == 0 {
            return Err(String::from("Aborted!"));
        }
        match input.to_lowercase().trim() {
            "y" | "yes" => return Ok(true),
            "n" | "no" | "" => return Ok(false),
            _ => println!("Error: invalid input"),
        }
    }
}

/// Read and confirm a password without echoing it to the terminal.
pub fn prompt_password() -> Result<String, String> {
    fn read_hidden(prompt: &str) -> Result<String, String> {
        let stdin = io::stdin();
        if !stdin.is_terminal() {
            eprint!("Warning: Password input may be echoed.\n{}", prompt);
            io::stderr().flush().map_err(|error| error.to_string())?;
            let mut input = String::new();
            if stdin
                .read_line(&mut input)
                .map_err(|error| error.to_string())?
                == 0
            {
                println!();
                return Err(String::from("Aborted!"));
            }
            eprintln!();
            return Ok(input.trim_end_matches(['\n', '\r']).to_owned());
        }
        use std::os::fd::AsRawFd;
        let fd = stdin.as_raw_fd();
        let mut original = unsafe { std::mem::zeroed::<libc::termios>() };
        if unsafe { libc::tcgetattr(fd, &mut original) } != 0 {
            return Err(format!(
                "Couldn't read terminal settings: {}",
                io::Error::last_os_error()
            ));
        }
        let mut hidden = original;
        hidden.c_lflag &= !libc::ECHO;
        if unsafe { libc::tcsetattr(fd, libc::TCSAFLUSH, &hidden) } != 0 {
            return Err(format!(
                "Couldn't disable terminal echo: {}",
                io::Error::last_os_error()
            ));
        }

        struct EchoGuard {
            fd: libc::c_int,
            original: libc::termios,
            active: bool,
        }

        impl EchoGuard {
            fn restore(&mut self) -> io::Result<()> {
                if self.active {
                    let result =
                        unsafe { libc::tcsetattr(self.fd, libc::TCSAFLUSH, &self.original) };
                    if result != 0 {
                        return Err(io::Error::last_os_error());
                    }
                    self.active = false;
                }
                Ok(())
            }
        }

        impl Drop for EchoGuard {
            fn drop(&mut self) {
                if self.active {
                    unsafe {
                        libc::tcsetattr(self.fd, libc::TCSAFLUSH, &self.original);
                    }
                }
            }
        }

        let mut echo = EchoGuard {
            fd,
            original,
            active: true,
        };
        eprint!("{}", prompt);
        io::stderr()
            .flush()
            .map_err(|error| format!("Failed to flush stderr: {}", error))?;
        let mut input = String::new();
        let read_result = stdin.read_line(&mut input);
        let restore_result = echo.restore();
        eprintln!();
        restore_result.map_err(|error| format!("Couldn't restore terminal echo: {}", error))?;
        let bytes = read_result.map_err(|error| format!("Failed to read password: {}", error))?;
        if bytes == 0 {
            return Err(String::from("Aborted!"));
        }
        Ok(input.trim_end_matches(['\n', '\r']).to_owned())
    }

    loop {
        let password = read_hidden("Password: ")?;
        if password.is_empty() {
            continue;
        }
        let confirmation = read_hidden("Repeat for confirmation: ")?;
        if password == confirmation {
            return Ok(password);
        }
        println!("Error: The two entered values do not match.");
    }
}

/// Format entry fields like Python's `str`, including collection representations.
pub fn scalar_string(value: &Yaml) -> String {
    fn quoted(value: &str) -> String {
        let quote = if value.contains('\'') && !value.contains('"') {
            '"'
        } else {
            '\''
        };
        let mut output = String::from(quote);
        for ch in value.chars() {
            match ch {
                '\n' => output.push_str("\\n"),
                '\r' => output.push_str("\\r"),
                '\t' => output.push_str("\\t"),
                '\\' => output.push_str("\\\\"),
                ch if ch == quote => {
                    output.push('\\');
                    output.push(ch);
                }
                ch if ch.is_control() => {
                    use std::fmt::Write;
                    let _ = write!(output, "\\x{:02x}", ch as u32);
                }
                ch => output.push(ch),
            }
        }
        output.push(quote);
        output
    }
    fn repr(value: &Yaml) -> String {
        match value {
            Yaml::String(value) => quoted(value),
            _ => scalar_string(value),
        }
    }
    match value {
        Yaml::String(value) => value.clone(),
        Yaml::Real(_) => {
            let number = value.as_f64().unwrap_or(f64::NAN);
            if number.is_nan() {
                String::from("nan")
            } else if number.is_infinite() {
                if number.is_sign_negative() {
                    String::from("-inf")
                } else {
                    String::from("inf")
                }
            } else {
                let text = format!("{:?}", number);
                if let Some((mantissa, exponent)) = text.split_once('e') {
                    let exponent: i32 = exponent.parse().expect("float exponent");
                    format!("{}e{:+03}", mantissa, exponent)
                } else {
                    text
                }
            }
        }
        Yaml::Integer(value) => value.to_string(),
        Yaml::Boolean(value) => if *value { "True" } else { "False" }.to_owned(),
        Yaml::Null => String::from("None"),
        Yaml::Array(values) => format!(
            "[{}]",
            values.iter().map(repr).collect::<Vec<_>>().join(", ")
        ),
        Yaml::Hash(values) => format!(
            "{{{}}}",
            values
                .iter()
                .map(|(key, value)| format!("{}: {}", repr(key), repr(value)))
                .collect::<Vec<_>>()
                .join(", ")
        ),
        _ => String::new(),
    }
}

/// Split a database path, allowing a trailing slash to mark a group.
pub fn path_parts(name: Option<&str>) -> Result<Vec<&str>, String> {
    let Some(name) = name else {
        return Ok(Vec::new());
    };
    let stripped = name.trim_end_matches('/');
    if stripped.is_empty() {
        return Ok(Vec::new());
    }
    let parts: Vec<&str> = stripped.split('/').collect();
    if parts.iter().any(|part| part.is_empty()) {
        return Err(format!("Invalid path: {}", name));
    }
    Ok(parts)
}

#[cfg(test)]
#[path = "../tests/unit/utils.rs"]
mod tests;
