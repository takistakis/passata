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
use crate::utils::{confirm, flag_or_setting, prompt_password};

/// Reject groups and confirm replacing an existing password, returning whether to proceed.
pub(crate) fn confirm_overwrite(
    db: &Database,
    name: &str,
    force: bool,
    mut confirm: impl FnMut(&str, bool) -> Result<bool, String>,
) -> Result<bool, String> {
    let node = db.get_optional(Some(name))?;
    if node.is_some_and(is_group) {
        return Err(format!("{} is a group", name));
    }
    let has_password = node
        .and_then(Yaml::as_hash)
        .is_some_and(|entry| entry.contains_key(&Yaml::String(String::from("password"))));
    Ok(!has_password || confirm(&format!("Overwrite {}?", name), force)?)
}

/// Insert a password, requiring confirmation only when replacing an existing password.
fn insert_into_database(
    db: &mut Database,
    name: &str,
    password: &str,
    force: bool,
    confirm: impl FnMut(&str, bool) -> Result<bool, String>,
) -> Result<bool, String> {
    if !confirm_overwrite(db, name, force, confirm)? {
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
    let name = args.get_one::<String>("name").unwrap();
    let force = flag_or_setting(args, config, root_config, "force");
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
