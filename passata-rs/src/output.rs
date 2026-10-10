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

use clap::ArgMatches;
use nu_ansi_term::Color::Blue;
use yaml_rust::Yaml;

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

/// Copy text with the platform clipboard command and apply a timeout in seconds.
///
/// On macOS, a positive timeout schedules clearing; zero disables scheduled clearing.
pub(crate) fn clipboard(data: &str, timeout: u64) -> Result<(), String> {
    #[cfg(target_os = "macos")]
    let mut child = Command::new("pbcopy")
        .stdin(Stdio::piped())
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
        .stderr(Stdio::null())
        .spawn()
        .map_err(|e| format!("Executable 'xsel' not found: {}", e))?;

    child
        .stdin
        .as_mut()
        .ok_or_else(|| String::from("Couldn't access clipboard command stdin"))?
        .write_all(data.as_bytes())
        .map_err(|e| format!("Couldn't write to clipboard: {}", e))?;
    let status = child
        .wait()
        .map_err(|e| format!("Couldn't wait for clipboard command: {}", e))?;
    if status.success() {
        #[cfg(target_os = "macos")]
        if timeout > 0 {
            let script = format!("sleep {} && printf '' | pbcopy", timeout);
            Command::new("/bin/sh")
                .args(["-c", &script])
                .stdin(Stdio::null())
                .stdout(Stdio::null())
                .stderr(Stdio::null())
                .spawn()
                .map_err(|e| format!("Couldn't schedule clipboard clearing: {}", e))?;
        }
        Ok(())
    } else {
        Err(format!("Clipboard command exited with status {}", status))
    }
}

/// Highlight YAML-style mapping keys and list markers with ANSI colors.
pub(crate) fn colorize(data: &str) -> String {
    let key = regex::Regex::new(r"(?m)^([ \t]*.*?)(:)([ \t]|$)").unwrap();
    let list_item = regex::Regex::new(r"(?m)^([ \t]*-[ \t])").unwrap();
    let keyed = key.replace_all(data, "\x1b[38;5;12m$1\x1b[38;5;11m:$3\x1b[0m");
    list_item
        .replace_all(&keyed, "\x1b[38;5;9m$1\x1b[0m")
        .into_owned()
}

/// Identify mappings whose children are all mappings, including empty groups.
fn is_group(value: &Yaml) -> bool {
    matches!(value, Yaml::Hash(map) if map.values().all(|child| matches!(child, Yaml::Hash(_))))
}

/// Append tree lines for string-keyed children, descending into groups only.
fn render_children(node: &Yaml, prefix: &str, color: bool, lines: &mut Vec<String>) {
    let Some(items) = node.as_hash() else {
        return;
    };
    let entries: Vec<_> = items.iter().collect();
    for (index, (key, value)) in entries.iter().enumerate() {
        let Some(name) = key.as_str() else {
            continue;
        };
        let last = index + 1 == entries.len();
        let connector = if last { "└── " } else { "├── " };
        let item = if is_group(value) && color {
            Blue.bold().paint(name).to_string()
        } else {
            name.to_owned()
        };
        lines.push(format!("{}{}{}", prefix, connector, item));
        if is_group(value) {
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
    let root = if color {
        Blue.bold().paint(label).to_string()
    } else {
        label.to_owned()
    };
    let mut lines = vec![root];
    render_children(node, "", color, &mut lines);
    lines.join("\n")
}

#[cfg(test)]
#[path = "../tests/unit/output.rs"]
mod tests;
