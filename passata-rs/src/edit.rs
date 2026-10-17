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
use std::path::{Path, PathBuf};
use std::process::{Child, Command};
use std::thread;
use std::time::{Duration, SystemTime, UNIX_EPOCH};

use yaml_rust::{Yaml, YamlLoader};

use crate::config_editor::editor_parts;
use crate::database::{Database, DatabaseHooks};
use crate::utils::path_parts;
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
        let mut options = std::fs::OpenOptions::new();
        options.write(true).create_new(true);
        #[cfg(unix)]
        {
            use std::os::unix::fs::OpenOptionsExt;
            options.mode(0o600);
        }
        match options.open(&path) {
            Ok(mut file) => {
                if let Err(error) = file.write_all(text.as_bytes()) {
                    let _ = std::fs::remove_file(&path);
                    return Err(format!("Couldn't write temporary edit file: {}", error));
                }
                return Ok(EditFile(path));
            }
            Err(error) if error.kind() == std::io::ErrorKind::AlreadyExists => continue,
            Err(error) => {
                return Err(format!("Couldn't create temporary edit file: {}", error));
            }
        }
    }
    Err(String::from("Couldn't create a unique temporary edit file"))
}

fn parse_edit_yaml(text: &str) -> Result<Yaml, String> {
    let mut documents =
        YamlLoader::load_from_str(text).map_err(|_| String::from("Invalid yaml"))?;
    if documents.len() > 1 {
        return Err(String::from("Invalid yaml"));
    }
    let value = documents
        .pop()
        .unwrap_or_else(|| Yaml::Hash(Default::default()));
    if !matches!(value, Yaml::Hash(_)) {
        return Err(String::from("Invalid yaml"));
    }
    Ok(value)
}

fn apply_edit(db: &mut Database, name: Option<&str>, value: Yaml) -> Result<(), String> {
    let mut updated = Database {
        path: db.path.clone(),
        db: db.db.clone(),
        data: db.data.clone(),
    };
    let target_name = if path_parts(name)?.is_empty() {
        None
    } else {
        name
    };
    let empty = value.as_hash().is_some_and(|map| map.is_empty());
    if empty {
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
    updated.validate()?;
    *db = updated;
    Ok(())
}

fn save_edit(
    db: &mut Database,
    name: Option<&str>,
    value: Yaml,
    gpg_id: &str,
    hooks: &mut DatabaseHooks,
) -> Result<(), String> {
    let mut updated = Database {
        path: db.path.clone(),
        db: db.db.clone(),
        data: db.data.clone(),
    };
    apply_edit(&mut updated, name, value)?;
    hooks.write(&mut updated, gpg_id)?;
    *db = updated;
    Ok(())
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
        Err(error) if error.kind() == std::io::ErrorKind::NotFound => return Ok(false),
        Err(error) => return Err(format!("Couldn't read temporary edit file: {}", error)),
    };
    if updated == *last_observed {
        return Ok(false);
    }
    *last_observed = updated.clone();
    let value = match parse_edit_yaml(&updated) {
        Ok(value) => value,
        Err(_) => {
            eprintln!("Invalid yaml, changes not saved");
            return Ok(false);
        }
    };
    if value.as_hash().is_some_and(|map| map.is_empty()) {
        return Ok(false);
    }
    save_edit(db, name, value, gpg_id, hooks)?;
    *last_saved = updated;
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
        let _ = observe_file(
            context.path,
            &mut last_observed,
            &mut last_saved,
            context.name,
            context.db,
            context.gpg_id,
            context.hooks,
        );
        if let Some(status) = child
            .try_wait()
            .map_err(|error| format!("Couldn't wait for editor: {}", error))?
        {
            let updated = std::fs::read_to_string(context.path)
                .map_err(|error| format!("Couldn't read temporary edit file: {}", error))?;
            if final_content_is_unsaved(&last_saved, &updated) {
                let value = parse_edit_yaml(&updated)?;
                save_edit(
                    context.db,
                    context.name,
                    value,
                    context.gpg_id,
                    context.hooks,
                )?;
            }
            if status.success() {
                return Ok(status);
            }
            return Err(format!("Editor '{}' exited with {}", program, status));
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
    let original = if current.as_hash().is_some_and(|map| map.is_empty()) {
        String::new()
    } else {
        yaml::dump(&current)?
    };
    let text = format!("# {}\n{}", name.unwrap_or("passata database"), original);
    let temporary_file = create_edit_file(&text)?;
    let mut command = editor_parts(args, command_config, root_config)?;
    let program = command.remove(0);
    let mut child = Command::new(&program)
        .args(command)
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
    let status = wait_for_editor(&mut child, &program, &text, &mut context)?;
    if status.success() {
        Ok(())
    } else {
        Err(format!("Editor '{}' exited with {}", program, status))
    }
}

#[cfg(test)]
#[path = "../tests/unit/edit.rs"]
mod tests;
