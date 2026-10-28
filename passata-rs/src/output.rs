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
use std::sync::LazyLock;

use clap::{ArgMatches, parser::ValueSource};
use nu_ansi_term::Color::Blue;
use regex::Regex;
use yaml_rust::Yaml;

use crate::database::is_group;

pub(crate) const DEFAULT_TIMEOUT: u64 = 45;

/// Resolve CLI and config color preferences against whether output is paged.
pub(crate) fn pager_color(
    args: &ArgMatches,
    configured_color: Option<bool>,
    pager_is_on: bool,
) -> bool {
    args.get_flag("color")
        || (!args.get_flag("no_color")
            && configured_color != Some(false)
            && (configured_color == Some(true) || pager_is_on))
}

/// Prefer an explicit `--timeout`, then the configured value, then the default.
pub(crate) fn clipboard_timeout(args: &ArgMatches, configured: Option<u64>) -> u64 {
    if args.value_source("timeout") == Some(ValueSource::CommandLine) {
        args.get_one::<u64>("timeout")
            .copied()
            .unwrap_or(DEFAULT_TIMEOUT)
    } else {
        configured.unwrap_or(DEFAULT_TIMEOUT)
    }
}

/// Format a node name, painting groups bold blue when colors are enabled.
pub(crate) fn group_label(name: &str, group: bool, color: bool) -> String {
    if group && color {
        Blue.bold().paint(name).to_string()
    } else {
        name.to_owned()
    }
}

/// Copy text with the platform clipboard command and apply a timeout in seconds.
///
/// On macOS, a positive timeout schedules clearing; zero disables scheduled clearing.
pub(crate) fn clipboard(data: &str, timeout: u64) -> Result<(), String> {
    #[cfg(target_os = "macos")]
    let mut child = Command::new("pbcopy")
        .stdin(Stdio::piped())
        .stderr(Stdio::piped())
        .spawn()
        .map_err(|e| format!("Executable 'pbcopy' not found: {}", e))?;
    #[cfg(not(target_os = "macos"))]
    let mut child = Command::new("xsel")
        .args([
            "-i",
            "-b",
            "-t",
            &(timeout.saturating_mul(1000)).to_string(),
        ])
        .stdin(Stdio::piped())
        .stderr(Stdio::piped())
        .spawn()
        .map_err(|e| format!("Executable 'xsel' not found: {}", e))?;

    child
        .stdin
        .as_mut()
        .ok_or_else(|| String::from("Couldn't access clipboard command stdin"))?
        .write_all(data.as_bytes())
        .map_err(|e| format!("Couldn't write to clipboard: {}", e))?;
    let output = child
        .wait_with_output()
        .map_err(|e| format!("Couldn't wait for clipboard command: {}", e))?;
    if output.status.success() {
        #[cfg(target_os = "macos")]
        if timeout > 0 {
            use std::os::unix::process::CommandExt;

            let script = format!("sleep {} && printf '' | pbcopy", timeout);
            let mut command = Command::new("/bin/sh");
            command
                .args(["-c", &script])
                .stdin(Stdio::null())
                .stdout(Stdio::null())
                .stderr(Stdio::null());
            // Only async-signal-safe session setup runs between fork and exec.
            unsafe {
                command.pre_exec(|| {
                    if libc::setsid() < 0 {
                        Err(std::io::Error::last_os_error())
                    } else {
                        Ok(())
                    }
                });
            }
            command
                .spawn()
                .map_err(|e| format!("Couldn't schedule clipboard clearing: {}", e))?;
        }
        Ok(())
    } else {
        Err(format!(
            "Clipboard command exited with status {}\n{}",
            output.status,
            String::from_utf8_lossy(&output.stderr).trim()
        ))
    }
}

/// Highlight YAML-style mapping keys and list markers with ANSI colors.
pub(crate) fn colorize(data: &str) -> String {
    static KEY: LazyLock<Regex> =
        LazyLock::new(|| Regex::new(r"(?m)^([ \t]*.*?)(:)([ \t]|$)").unwrap());
    static LIST_ITEM: LazyLock<Regex> =
        LazyLock::new(|| Regex::new(r"(?m)^([ \t]*-[ \t])").unwrap());
    let keyed = KEY.replace_all(data, "\x1b[38;5;12m$1\x1b[38;5;11m:\x1b[0m$3");
    LIST_ITEM
        .replace_all(&keyed, "\x1b[38;5;9m$1\x1b[0m")
        .into_owned()
}

/// Append tree lines for string-keyed children, descending into groups only.
fn render_children(node: &Yaml, prefix: &str, color: bool, lines: &mut Vec<String>) {
    let Some(items) = node.as_hash() else {
        return;
    };
    for (index, (key, value)) in items.iter().enumerate() {
        let Some(name) = key.as_str() else {
            continue;
        };
        let last = index + 1 == items.len();
        let connector = if last { "└── " } else { "├── " };
        let group = is_group(value);
        lines.push(format!(
            "{}{}{}",
            prefix,
            connector,
            group_label(name, group, color)
        ));
        if group {
            let extension = if last { "    " } else { "│   " };
            render_children(value, &format!("{}{}", prefix, extension), color, lines);
        }
    }
}

/// Render a labeled tree with optional group colors, returning no text for an empty root.
pub(crate) fn render_tree(node: &Yaml, label: &str, color: bool) -> String {
    if node.as_hash().is_none_or(|items| items.is_empty()) {
        return String::new();
    }
    let mut lines = vec![group_label(label, true, color)];
    render_children(node, "", color, &mut lines);
    lines.join("\n")
}

#[cfg(test)]
#[path = "../tests/unit/output.rs"]
mod tests;
