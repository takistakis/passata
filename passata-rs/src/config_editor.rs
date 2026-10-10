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

use crate::config_value;

fn editor_setting<'a>(config: Option<&'a Yaml>, root: &'a Yaml) -> Option<&'a str> {
    config
        .and_then(|config| config_value(config, "editor"))
        .or_else(|| config_value(root, "editor"))
        .and_then(Yaml::as_str)
}

/// Open the configuration file in the selected editor, inheriting its terminal streams.
pub fn edit(
    config_path: &Path,
    args: &clap::ArgMatches,
    command_config: Option<&Yaml>,
    root_config: &Yaml,
) -> Result<(), String> {
    let editor = args
        .get_one::<String>("editor")
        .map(String::as_str)
        .or_else(|| editor_setting(command_config, root_config))
        .map(str::to_owned)
        .or_else(|| std::env::var("EDITOR").ok())
        .unwrap_or_else(|| String::from("vim"));
    let mut command = shlex::split(&editor)
        .filter(|parts| !parts.is_empty())
        .ok_or_else(|| format!("Invalid editor command: {}", editor))?;
    let program = command.remove(0);
    let status = Command::new(&program)
        .args(command)
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
