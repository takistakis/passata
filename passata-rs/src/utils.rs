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

use std::io::{self, IsTerminal, Write};

use yaml_rust::Yaml;

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
        io::stdin()
            .read_line(&mut input)
            .map_err(|e| format!("Failed to read from stdin: {}", e))?;
        match input.to_lowercase().trim() {
            "y" | "yes" => return Ok(true),
            "n" | "no" | "" => return Ok(false),
            _ => continue,
        }
    }
}

/// Read and confirm a password without echoing it to the terminal.
pub fn prompt_password() -> Result<String, String> {
    fn read_hidden(prompt: &str) -> Result<String, String> {
        let stdin = io::stdin();
        if !stdin.is_terminal() {
            return Err(String::from(
                "Password prompt requires a terminal; use --password",
            ));
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
        let confirmation = read_hidden("Repeat for confirmation: ")?;
        if password == confirmation {
            return Ok(password);
        }
        eprintln!("Error: Passwords do not match.");
    }
}

/// Format YAML scalars as text, using `None` for null and empty text for unsupported values.
pub fn scalar_string(value: &Yaml) -> String {
    match value {
        Yaml::String(value) | Yaml::Real(value) => value.clone(),
        Yaml::Integer(value) => value.to_string(),
        Yaml::Boolean(value) => value.to_string(),
        Yaml::Null => String::from("None"),
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
