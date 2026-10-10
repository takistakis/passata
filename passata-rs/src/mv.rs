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

fn is_group_dest(db: &Database, dest: &str) -> Result<bool, String> {
    let node = db.get_optional(Some(dest))?;
    Ok(dest.ends_with('/') || node.is_some_and(is_group))
}

/// Apply moves to a copy so errors or declined overwrites leave the database unchanged.
fn move_paths(
    db: &mut Database,
    sources: &[String],
    dest: &str,
    force: bool,
    mut confirm: impl FnMut(&str, bool) -> Result<bool, String>,
) -> Result<bool, String> {
    if sources.is_empty() {
        return Err(String::from("At least one source is required"));
    }
    let mut pending = Database {
        path: db.path.clone(),
        db: db.db.clone(),
        data: None,
    };
    let group_dest = is_group_dest(db, dest)?;
    if sources.len() > 1 && !group_dest {
        return Err(format!("{} is not a group", dest));
    }
    let dest = dest.trim_end_matches('/');
    for source in sources {
        let src = source.trim_end_matches('/');
        if path_parts(Some(src))?.is_empty() {
            return Err(String::from("Cannot move the whole database"));
        }
        let node = pending.get(Some(src))?;
        if node.as_hash().is_none() {
            return Err(format!("{} is not an entry or group", src));
        }
        let group = is_group(node);
        let newname = if sources.len() == 1 && group {
            if pending.get_optional(Some(dest))?.is_some() {
                return Err(format!("{} already exists", dest));
            }
            dest.to_owned()
        } else if group_dest {
            let leaf = path_parts(Some(src))?.last().unwrap().to_string();
            if dest.is_empty() {
                leaf
            } else {
                format!("{}/{}", dest, leaf)
            }
        } else {
            dest.to_owned()
        };
        if group && newname.starts_with(&format!("{}/", src)) {
            return Err(format!("Cannot move '{}' into its own subdirectory", src));
        }
        if !(sources.len() == 1 && group)
            && pending.get_optional(Some(&newname))?.is_some()
            && !confirm(&format!("Overwrite {}?", newname), force)?
        {
            return Ok(false);
        }
        let node = pending.pop(src)?;
        pending.put(&newname, node)?;
    }
    db.db = pending.db;
    Ok(true)
}

/// Move entries under an exclusive lock, persisting only a fully accepted operation.
pub fn mv(
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
    let sources: Vec<String> = args
        .get_many::<String>("source")
        .unwrap()
        .cloned()
        .collect();
    let dest = args.get_one::<String>("dest").unwrap();
    let mut db = hooks.read(database_path, true)?;
    if move_paths(&mut db, &sources, dest, force, confirm)? {
        hooks.write(&mut db, gpg_id)?;
    }
    Ok(())
}

#[cfg(test)]
#[path = "../tests/unit/mv.rs"]
mod tests;
