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

use std::path::Path;
use std::process::Command;

use yaml_rust::Yaml;

use crate::utils::config_setting;

/// Resolve the editor command from the CLI, configuration, `$EDITOR`, or `vim`.
pub(crate) fn editor_parts(
    args: &clap::ArgMatches,
    command_config: Option<&Yaml>,
    root_config: &Yaml,
) -> Result<Vec<String>, String> {
    let editor = args
        .get_one::<String>("editor")
        .map(String::as_str)
        .or_else(|| config_setting(command_config, root_config, "editor").and_then(Yaml::as_str))
        .map(str::to_owned)
        .or_else(|| std::env::var("EDITOR").ok())
        .unwrap_or_else(|| String::from("vim"));
    shlex::split(&editor)
        .filter(|parts| !parts.is_empty())
        .ok_or_else(|| format!("Invalid editor command: {}", editor))
}

/// Split the editor command into its program and leading arguments.
pub(crate) fn editor_command(
    args: &clap::ArgMatches,
    command_config: Option<&Yaml>,
    root_config: &Yaml,
) -> Result<(String, Vec<String>), String> {
    let mut parts = editor_parts(args, command_config, root_config)?;
    let program = parts.remove(0);
    Ok((program, parts))
}

/// Open the configuration file in the selected editor, inheriting its terminal streams.
pub fn edit(
    config_path: &Path,
    args: &clap::ArgMatches,
    command_config: Option<&Yaml>,
    root_config: &Yaml,
) -> Result<(), String> {
    let (program, editor_args) = editor_command(args, command_config, root_config)?;
    let status = Command::new(&program)
        .args(editor_args)
        .arg(config_path)
        .status()
        .map_err(|error| format!("Couldn't execute editor '{}': {}", program, error))?;
    if status.success() {
        Ok(())
    } else {
        Err(format!("Editor '{}' exited with {}", program, status))
    }
}

#[cfg(test)]
#[path = "../tests/unit/config_editor.rs"]
mod tests;
