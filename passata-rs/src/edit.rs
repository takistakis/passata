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

use std::io::{ErrorKind, Write};
use std::path::{Path, PathBuf};
use std::process::{Child, Command};
use std::thread;
use std::time::{Duration, SystemTime, UNIX_EPOCH};

use yaml_rust::Yaml;

use crate::config_editor::editor_command;
use crate::database::{Database, DatabaseHooks, is_group};
use crate::utils::{confirm, create_private_file, path_parts};
use crate::yaml;

struct EditFile(PathBuf);

impl Drop for EditFile {
    fn drop(&mut self) {
        let _ = std::fs::remove_file(&self.0);
    }
}

fn create_edit_file(text: &str) -> Result<EditFile, String> {
    let directory = std::env::temp_dir();
    let timestamp = SystemTime::now()
        .duration_since(UNIX_EPOCH)
        .map_err(|error| error.to_string())?
        .as_nanos();
    for attempt in 0..100 {
        let path = directory.join(format!(
            "passata-{}-{}-{}.yml",
            std::process::id(),
            timestamp,
            attempt
        ));
        match create_private_file(&path) {
            Ok(mut file) => {
                if let Err(error) = file.write_all(text.as_bytes()) {
                    let _ = std::fs::remove_file(&path);
                    return Err(format!("Couldn't write temporary edit file: {}", error));
                }
                return Ok(EditFile(path));
            }
            Err(error) if error.kind() == ErrorKind::AlreadyExists => continue,
            Err(error) => {
                return Err(format!("Couldn't create temporary edit file: {}", error));
            }
        }
    }
    Err(String::from("Couldn't create a unique temporary edit file"))
}

fn parse_edit_yaml(text: &str) -> Result<Yaml, String> {
    let mut documents = yaml::load(text).map_err(|_| String::from("Invalid yaml"))?;
    if documents.len() > 1 {
        return Err(String::from("Invalid yaml"));
    }
    let value = documents
        .pop()
        .unwrap_or_else(|| Yaml::Hash(Default::default()));
    if matches!(value, Yaml::Null) {
        return Ok(Yaml::Hash(Default::default()));
    }
    if !matches!(value, Yaml::Hash(_)) {
        return Err(String::from("Invalid yaml"));
    }
    Ok(value)
}

fn is_empty_mapping(value: &Yaml) -> bool {
    value.as_hash().is_some_and(|map| map.is_empty())
}

/// Replace or delete the edited node in place and validate the result.
///
/// Callers apply edits to a copy so failures leave the original database unchanged.
fn apply_edit(updated: &mut Database, name: Option<&str>, value: Yaml) -> Result<(), String> {
    let target_name = if path_parts(name)?.is_empty() {
        None
    } else {
        name
    };
    if is_empty_mapping(&value) {
        if let Some(name) = target_name {
            if updated.get_optional(Some(name))?.is_some() {
                updated.pop(name)?;
            }
        } else if let Yaml::Hash(map) = &mut updated.db {
            map.clear();
        }
    } else if let Some(name) = target_name {
        updated.put(name, value)?;
    } else {
        updated.db = value;
    }
    updated.validate()
}

fn save_edit(
    db: &mut Database,
    name: Option<&str>,
    value: Yaml,
    gpg_id: &str,
    hooks: &mut DatabaseHooks,
) -> Result<(), String> {
    let mut updated = db.clone();
    apply_edit(&mut updated, name, value)?;
    hooks.write(&mut updated, gpg_id)?;
    *db = updated;
    Ok(())
}

fn confirm_deletion(db: &Database, name: Option<&str>, value: &Yaml) -> Result<bool, String> {
    if !is_empty_mapping(value) {
        return Ok(true);
    }
    if path_parts(name)?.is_empty() {
        return confirm("Delete the whole database?", false);
    }
    let Some(node) = db.get_optional(name)? else {
        return Ok(true);
    };
    let label = if is_group(node) { "group " } else { "" };
    confirm(
        &format!("Delete {}'{}'?", label, name.unwrap_or_default()),
        false,
    )
}

fn final_content_is_unsaved(last_saved: &str, updated: &str) -> bool {
    updated != last_saved
}

fn observe_file(
    path: &Path,
    last_observed: &mut String,
    last_saved: &mut String,
    name: Option<&str>,
    db: &mut Database,
    gpg_id: &str,
    hooks: &mut DatabaseHooks,
) -> Result<bool, String> {
    let updated = match std::fs::read_to_string(path) {
        Ok(updated) => updated,
        Err(error) if error.kind() == ErrorKind::NotFound => return Ok(false),
        Err(error) => return Err(format!("Couldn't read temporary edit file: {}", error)),
    };
    if updated == *last_observed {
        return Ok(false);
    }
    let parsed = parse_edit_yaml(&updated);
    *last_observed = updated;
    let Ok(value) = parsed else {
        eprintln!("Invalid yaml, changes not saved");
        return Ok(false);
    };
    if is_empty_mapping(&value) {
        return Ok(false);
    }
    save_edit(db, name, value, gpg_id, hooks)?;
    last_saved.clone_from(last_observed);
    Ok(true)
}

struct EditorContext<'a> {
    path: &'a Path,
    name: Option<&'a str>,
    db: &'a mut Database,
    gpg_id: &'a str,
    hooks: &'a mut DatabaseHooks,
}

fn wait_for_editor(
    child: &mut Child,
    program: &str,
    initial_text: &str,
    context: &mut EditorContext<'_>,
) -> Result<std::process::ExitStatus, String> {
    let mut last_observed = initial_text.to_owned();
    let mut last_saved = initial_text.to_owned();
    loop {
        if let Some(status) = child
            .try_wait()
            .map_err(|error| format!("Couldn't wait for editor: {}", error))?
        {
            if !status.success() {
                return Err(format!("Editor '{}' exited with {}", program, status));
            }
            let updated = std::fs::read_to_string(context.path)
                .map_err(|error| format!("Couldn't read temporary edit file: {}", error))?;
            if final_content_is_unsaved(&last_saved, &updated) {
                let value = parse_edit_yaml(&updated)?;
                if confirm_deletion(context.db, context.name, &value)? {
                    save_edit(
                        context.db,
                        context.name,
                        value,
                        context.gpg_id,
                        context.hooks,
                    )?;
                }
            }
            return Ok(status);
        }
        if let Err(error) = observe_file(
            context.path,
            &mut last_observed,
            &mut last_saved,
            context.name,
            context.db,
            context.gpg_id,
            context.hooks,
        ) {
            eprintln!("{}, changes not saved", error);
        }
        thread::sleep(Duration::from_millis(100));
    }
}

/// Edit an entry, group, or the complete database in an external editor.
pub fn edit(
    database_path: &str,
    args: &clap::ArgMatches,
    command_config: Option<&Yaml>,
    root_config: &Yaml,
    gpg_id: &str,
    hooks: &mut DatabaseHooks,
) -> Result<(), String> {
    let name = args.get_one::<String>("name").map(String::as_str);
    let mut db = hooks.read(database_path, true)?;
    let current = db
        .get_optional(name)?
        .cloned()
        .unwrap_or_else(|| Yaml::Hash(Default::default()));
    let original = if is_empty_mapping(&current) {
        String::new()
    } else {
        yaml::dump(&current)?
    };
    let text = format!("# {}\n{}", name.unwrap_or("passata database"), original);
    let temporary_file = create_edit_file(&text)?;
    let (program, editor_args) = editor_command(args, command_config, root_config)?;
    let mut child = Command::new(&program)
        .args(editor_args)
        .arg(&temporary_file.0)
        .spawn()
        .map_err(|error| format!("Couldn't execute editor '{}': {}", program, error))?;
    let mut context = EditorContext {
        path: &temporary_file.0,
        name,
        db: &mut db,
        gpg_id,
        hooks,
    };
    wait_for_editor(&mut child, &program, &text, &mut context)?;
    Ok(())
}

#[cfg(test)]
#[path = "../tests/unit/edit.rs"]
mod tests;
