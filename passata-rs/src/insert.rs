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
use crate::utils::{confirm, prompt_password};

/// Insert a password, requiring confirmation only when replacing an existing password.
fn insert_into_database(
    db: &mut Database,
    name: &str,
    password: &str,
    force: bool,
    mut confirm: impl FnMut(&str, bool) -> Result<bool, String>,
) -> Result<bool, String> {
    if db.get_optional(Some(name))?.is_some_and(is_group) {
        return Err(format!("{} is a group", name));
    }

    let has_password = db
        .get_optional(Some(name))?
        .and_then(Yaml::as_hash)
        .is_some_and(|entry| entry.contains_key(&Yaml::String(String::from("password"))));
    if has_password && !confirm(&format!("Overwrite {}?", name), force)? {
        return Ok(false);
    }

    db.insert_password(name, password)?;
    Ok(true)
}

/// Insert a password under an exclusive lock and preserve any replaced password.
pub fn insert(
    database_path: &str,
    args: &clap::ArgMatches,
    config: Option<&Yaml>,
    root_config: &Yaml,
    gpg_id: &str,
    hooks: &mut DatabaseHooks,
) -> Result<(), String> {
    let setting = |key: &str| {
        config
            .and_then(|config| crate::config_value(config, key))
            .or_else(|| crate::config_value(root_config, key))
    };
    let name = args.get_one::<String>("name").unwrap();
    let force = args.get_flag("force") || setting("force").and_then(Yaml::as_bool).unwrap_or(false);
    let password = match args.get_one::<String>("password") {
        Some(password) => password.clone(),
        None => prompt_password()?,
    };

    let mut db = hooks.read(database_path, true)?;
    if insert_into_database(&mut db, name, &password, force, confirm)? {
        hooks.write(&mut db, gpg_id)?;
    }
    Ok(())
}

#[cfg(test)]
#[path = "../tests/unit/insert.rs"]
mod tests;
