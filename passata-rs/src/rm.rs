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

use yaml_rust::Yaml;

use crate::database::{Database, DatabaseHooks, is_group};
use crate::utils::{confirm, path_parts};

/// Remove entries or groups from a copy so cancelled or failed requests are not persisted.
fn remove_paths(
    db: &mut Database,
    names: &[String],
    force: bool,
    recursive: bool,
    mut confirm: impl FnMut(&str, bool) -> Result<bool, String>,
) -> Result<bool, String> {
    if names.is_empty() {
        return Err(String::from("At least one name is required"));
    }

    for name in names {
        if db.get_optional(Some(name))?.is_some_and(is_group) && !recursive {
            return Err(format!(
                "Cannot remove '{}': is a group, use -r to remove",
                name
            ));
        }
    }

    let mut pending = Database {
        path: db.path.clone(),
        db: db.db.clone(),
        data: None,
    };
    let force = if names.len() > 1 {
        if !confirm(&format!("Delete {} arguments?", names.len()), force)? {
            return Ok(false);
        }
        true
    } else {
        force
    };

    for name in names {
        let parts = path_parts(Some(name))?;
        if parts.is_empty() {
            if !confirm("Delete the whole database?", force)? {
                return Ok(false);
            }
            if let Yaml::Hash(map) = &mut pending.db {
                map.clear();
            } else {
                return Err(String::from("Invalid database format"));
            }
            continue;
        }

        let node = pending
            .get_optional(Some(name))?
            .ok_or_else(|| format!("{} not found", name))?;
        let label = if is_group(node) { "group " } else { "" };
        if !confirm(&format!("Delete {}'{}'?", label, name), force)? {
            return Ok(false);
        }
        pending.pop(name)?;
    }

    db.db = pending.db;
    Ok(true)
}

/// Remove entries under an exclusive lock, persisting only a fully accepted operation.
pub fn rm(
    database_path: &str,
    args: &clap::ArgMatches,
    config: Option<&Yaml>,
    root_config: &Yaml,
    gpg_id: &str,
    hooks: &mut DatabaseHooks,
) -> Result<(), String> {
    let force = args.get_flag("force")
        || config
            .and_then(|config| crate::config_value(config, "force"))
            .or_else(|| crate::config_value(root_config, "force"))
            .and_then(Yaml::as_bool)
            .unwrap_or(false);
    let names: Vec<String> = args.get_many::<String>("names").unwrap().cloned().collect();
    let recursive = args.get_flag("recursive");
    let mut db = hooks.read(database_path, true)?;
    if remove_paths(&mut db, &names, force, recursive, confirm)? {
        hooks.write(&mut db, gpg_id)?;
    }
    Ok(())
}

#[cfg(test)]
#[path = "../tests/unit/rm.rs"]
mod tests;
