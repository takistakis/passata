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
use std::path::{Path, PathBuf};
use std::process::Command;

use clap::ArgMatches;
use yaml_rust::Yaml;

use crate::database::{Database, DatabaseLock};
use crate::utils::confirm;

/// Find the first email-style identifier printed by `gpg --list-secret-keys`.
fn default_gpg_id() -> Result<String, String> {
    let output = Command::new("gpg")
        .arg("--list-secret-keys")
        .output()
        .map_err(|error| format!("Couldn't execute gpg: {}", error))?;
    if !output.status.success() {
        return Err(format!(
            "gpg --list-secret-keys failed: {}",
            String::from_utf8_lossy(&output.stderr).trim()
        ));
    }
    let listing = String::from_utf8_lossy(&output.stdout);
    listing
        .lines()
        .find_map(|line| {
            let start = line.find('<')?;
            let end = line[start + 1..].find('>')? + start + 1;
            let id = &line[start + 1..end];
            (!id.is_empty()).then(|| id.to_owned())
        })
        .ok_or_else(|| String::from("No gpg secret keys found"))
}

/// Prompt for a value, accepting its default when the user enters an empty line.
fn prompt_value(label: &str, default: &str) -> Result<String, String> {
    if !io::stdin().is_terminal() {
        return Err(format!(
            "{} prompt requires a terminal; provide the corresponding option",
            label
        ));
    }
    print!("{} [{}]: ", label, default);
    io::stdout()
        .flush()
        .map_err(|error| format!("Failed to flush stdout: {}", error))?;
    let mut value = String::new();
    let bytes = io::stdin()
        .read_line(&mut value)
        .map_err(|error| format!("Failed to read {}: {}", label, error))?;
    if bytes == 0 {
        return Err(String::from("Aborted!"));
    }
    let value = value.trim_end_matches(['\n', '\r']);
    Ok(if value.is_empty() {
        default.to_owned()
    } else {
        value.to_owned()
    })
}

/// Make a path absolute without requiring that its target already exists.
fn absolute(path: PathBuf) -> Result<PathBuf, String> {
    if path.is_absolute() {
        Ok(path)
    } else {
        std::env::current_dir()
            .map(|directory| directory.join(path))
            .map_err(|error| format!("Couldn't determine current directory: {}", error))
    }
}

/// Write the database configuration after confirming any existing-file overwrite.
fn write_config(
    path: &Path,
    database_path: &Path,
    gpg_id: &str,
    force: bool,
) -> Result<bool, String> {
    if path.is_file() && !confirm(&format!("Overwrite {}?", path.display()), force)? {
        return Ok(false);
    }
    let parent = path
        .parent()
        .filter(|parent| !parent.as_os_str().is_empty())
        .unwrap_or_else(|| Path::new("."));
    std::fs::create_dir_all(parent)
        .map_err(|error| format!("Couldn't create configuration directory: {}", error))?;

    let mut values = yaml_rust::yaml::Hash::new();
    values.insert(
        Yaml::String(String::from("database")),
        Yaml::String(database_path.to_string_lossy().into_owned()),
    );
    values.insert(
        Yaml::String(String::from("gpg_id")),
        Yaml::String(gpg_id.to_owned()),
    );
    let contents = crate::yaml::dump(&Yaml::Hash(values))?;
    std::fs::write(path, contents)
        .map_err(|error| format!("Couldn't write configuration {}: {}", path.display(), error))?;
    Ok(true)
}

/// Initialize a config file and an empty, GPG-encrypted database.
pub fn initialize(config_path: &Path, args: &ArgMatches) -> Result<(), String> {
    let force = args.get_flag("force");
    let gpg_id = match args.get_one::<String>("gpg_id") {
        Some(gpg_id) => gpg_id.clone(),
        None => {
            let default = default_gpg_id()?;
            prompt_value("GnuPG ID", &default)?
        }
    };
    let path = match args.get_one::<String>("path") {
        Some(path) => path.clone(),
        None => prompt_value("Database path", "~/.passata.gpg")?,
    };
    let database_path = absolute(crate::expand_home(&path))?;
    if database_path.is_dir() {
        return Err(format!(
            "Database path {} is a directory",
            database_path.display()
        ));
    }

    let _lock = DatabaseLock::acquire(&database_path.to_string_lossy())?;
    if !write_config(config_path, &database_path, &gpg_id, force)? {
        return Ok(());
    }

    if database_path.is_file()
        && !confirm(&format!("Overwrite {}?", database_path.display()), force)?
    {
        return Ok(());
    }
    let mut database = Database {
        path: database_path.to_string_lossy().into_owned(),
        db: Yaml::Hash(Default::default()),
        data: None,
    };
    database.write_encrypted(&gpg_id)?;
    Ok(())
}

#[cfg(test)]
#[path = "../tests/unit/init.rs"]
mod tests;
