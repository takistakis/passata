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

use std::fmt::{self, Display, Formatter};
use std::path::{Path, PathBuf};
use std::process::{Command, Stdio};

use gpgme::{Context, Protocol};
use yaml_rust::Yaml;

use crate::utils::{create_private_file, path_parts, scalar_string};

/// Decrypt an OpenPGP file with GPGME and decode its contents as UTF-8.
fn decrypt(path: &str) -> Result<String, String> {
    let mut ctx = Context::from_protocol(Protocol::OpenPgp).map_err(|e| e.to_string())?;
    let mut output = Vec::new();
    let mut input = std::fs::File::open(path).map_err(|e| e.to_string())?;
    ctx.decrypt(&mut input, &mut output)
        .map_err(|e| format!("Couldn't decrypt database: {}", e))?;
    String::from_utf8(output).map_err(|e| e.to_string())
}

/// Identify a nonempty mapping containing at least one non-mapping field.
pub(crate) fn is_entry(value: &Yaml) -> bool {
    match value {
        Yaml::Hash(map) if !map.is_empty() => map.values().any(|v| !matches!(v, Yaml::Hash(_))),
        _ => false,
    }
}

/// Convert a field or path component into a YAML string key.
fn map_key(name: &str) -> Yaml {
    Yaml::String(name.to_owned())
}

/// Resolve parent groups, creating any that are missing.
fn parent_group_mut<'a>(root: &'a mut Yaml, parents: &[&str]) -> Result<&'a mut Yaml, String> {
    let mut current = root;
    for part in parents {
        let map = match current {
            Yaml::Hash(map) => map,
            _ => return Err(String::from("Invalid database format")),
        };
        current = map
            .entry(map_key(part))
            .or_insert_with(|| Yaml::Hash(Default::default()));
        if is_entry(current) {
            return Err(format!("'{}' is an entry, cannot create subpath", part));
        }
    }
    Ok(current)
}

#[derive(Clone)]
pub struct Database {
    pub path: String,
    pub db: Yaml,
    pub data: Option<String>,
}

pub struct DatabaseLock {
    file: std::fs::File,
}

impl Drop for DatabaseLock {
    fn drop(&mut self) {
        use std::os::unix::io::AsRawFd;

        // Explicitly unlock even if another thread forked and temporarily inherited the fd.
        if unsafe { libc::flock(self.file.as_raw_fd(), libc::LOCK_UN) } != 0 {
            eprintln!(
                "Couldn't unlock database: {}",
                std::io::Error::last_os_error()
            );
        }
    }
}

pub struct DatabaseHooks {
    pre_read: Option<PathBuf>,
    post_write: Option<PathBuf>,
    written: bool,
    lock: Option<DatabaseLock>,
}

impl DatabaseHooks {
    pub fn new(config_path: &Path) -> Self {
        let directory = config_path.parent().unwrap_or_else(|| Path::new("."));
        let hook = |name| {
            let path = directory.join("hooks").join(name);
            path.is_file().then_some(path)
        };
        Self {
            pre_read: hook("pre-read"),
            post_write: hook("post-write"),
            written: false,
            lock: None,
        }
    }

    pub fn read(&mut self, path: &str, lock: bool) -> Result<Database, String> {
        if let Some(hook) = &self.pre_read {
            execute_hook(hook)?;
        }
        if !Path::new(path).is_file() {
            return Err(format!("Database file ({}) does not exist", path));
        }
        if lock && self.lock.is_none() {
            self.lock = Some(DatabaseLock::acquire(path)?);
        }
        Database::new(path.to_owned())
    }

    pub fn write(&mut self, database: &mut Database, recipient: &str) -> Result<(), String> {
        if database.write_encrypted(recipient)? {
            self.written = true;
        }
        Ok(())
    }

    /// Run once after command output and clipboard handling, while still holding the lock.
    pub fn finish(&mut self) -> Result<(), String> {
        if std::mem::take(&mut self.written) {
            if let Some(hook) = &self.post_write {
                execute_hook(hook)?;
            }
        }
        Ok(())
    }
}

fn execute_hook(path: &Path) -> Result<(), String> {
    let output = Command::new(path)
        .stdin(Stdio::inherit())
        .stdout(Stdio::inherit())
        .output()
        .map_err(|error| {
            if error.kind() == std::io::ErrorKind::NotFound {
                format!("Executable '{}' not found", path.display())
            } else {
                format!("Couldn't execute hook '{}': {}", path.display(), error)
            }
        })?;
    if !output.status.success() {
        return Err(format!(
            "Hook '{}' failed with {}\n{}",
            path.display(),
            output.status,
            String::from_utf8_lossy(&output.stderr).trim()
        ));
    }
    Ok(())
}

impl DatabaseLock {
    /// Acquire a nonblocking exclusive lock, held until this guard is dropped.
    ///
    /// The hidden lock file is left in place so concurrent processes lock the same inode.
    pub fn acquire(database_path: &str) -> Result<DatabaseLock, String> {
        use std::os::unix::fs::OpenOptionsExt;
        use std::os::unix::io::AsRawFd;

        let path = lock_file_path(database_path)?;
        let file = std::fs::OpenOptions::new()
            .create(true)
            .append(true)
            .mode(0o600)
            .custom_flags(libc::O_NOFOLLOW)
            .open(&path)
            .map_err(|e| format!("Couldn't open lock file {}: {}", path.display(), e))?;
        let result = unsafe { libc::flock(file.as_raw_fd(), libc::LOCK_EX | libc::LOCK_NB) };
        if result != 0 {
            let error = std::io::Error::last_os_error();
            return Err(
                if matches!(error.raw_os_error(), Some(libc::EAGAIN | libc::EACCES)) {
                    String::from("Another passata process is editing the database")
                } else {
                    format!("Couldn't lock database: {}", error)
                },
            );
        }
        Ok(DatabaseLock { file })
    }
}

fn lock_file_path(database_path: &str) -> Result<PathBuf, String> {
    use std::os::unix::ffi::OsStrExt;
    use std::os::unix::fs::{MetadataExt, PermissionsExt};

    let path = Path::new(database_path);
    let canonical_path = match path.canonicalize() {
        Ok(path) => path,
        Err(error) if error.kind() == std::io::ErrorKind::NotFound => {
            let name = path
                .file_name()
                .ok_or_else(|| format!("Invalid database path: {}", database_path))?;
            let parent = path
                .parent()
                .filter(|parent| !parent.as_os_str().is_empty())
                .unwrap_or_else(|| Path::new("."))
                .canonicalize()
                .map_err(|error| format!("Couldn't resolve database directory: {}", error))?;
            parent.join(name)
        }
        Err(error) => return Err(format!("Couldn't resolve database path: {}", error)),
    };

    let state_home = std::env::var_os("XDG_STATE_HOME")
        .map(PathBuf::from)
        .or_else(|| std::env::var_os("HOME").map(|home| PathBuf::from(home).join(".local/state")))
        .ok_or_else(|| String::from("Couldn't determine the state directory"))?;
    let directory = state_home.join("passata").join("locks");
    std::fs::create_dir_all(&directory)
        .map_err(|error| format!("Couldn't create lock directory: {}", error))?;
    let metadata = std::fs::symlink_metadata(&directory)
        .map_err(|error| format!("Couldn't inspect lock directory: {}", error))?;
    if !metadata.file_type().is_dir() || metadata.uid() != unsafe { libc::geteuid() } {
        return Err(String::from(
            "Lock directory must be a directory owned by the current user",
        ));
    }
    std::fs::set_permissions(&directory, std::fs::Permissions::from_mode(0o700))
        .map_err(|error| format!("Couldn't secure lock directory: {}", error))?;

    let hash = canonical_path
        .as_os_str()
        .as_bytes()
        .iter()
        .fold(0xcbf29ce484222325_u64, |hash, byte| {
            (hash ^ u64::from(*byte)).wrapping_mul(0x100000001b3)
        });
    Ok(directory.join(format!("database-{hash:016x}.lock")))
}

impl Database {
    /// Decrypt and validate a database, treating an empty file as an empty mapping.
    pub fn new(path: String) -> Result<Database, String> {
        if !Path::new(&path).is_file() {
            return Err(format!("Database file ({}) does not exist", path));
        }
        let output = decrypt(&path)?;
        let mut docs =
            crate::yaml::load(&output).map_err(|e| format!("Invalid database YAML: {}", e))?;
        if docs.len() > 1 {
            return Err(String::from("Invalid database YAML: multiple documents"));
        }
        let db = if docs.is_empty() {
            Yaml::Hash(Default::default())
        } else {
            docs.remove(0)
        };
        let database = Database {
            path,
            db,
            data: Some(output),
        };
        database.validate()?;
        Ok(database)
    }

    /// Serialize a database node as YAML without a document marker.
    pub fn yaml_for(&self, value: &Yaml) -> Result<String, String> {
        crate::yaml::dump(value)
    }

    /// Collect entry paths and nodes in traversal order, excluding groups.
    pub fn entries(&self) -> Vec<(String, &Yaml)> {
        /// Traverse groups recursively and append their descendant entries.
        fn walk<'a>(node: &'a Yaml, prefix: &str, entries: &mut Vec<(String, &'a Yaml)>) {
            if let Some(map) = node.as_hash() {
                for (key, value) in map {
                    if let Some(key) = key.as_str() {
                        let path = if prefix.is_empty() {
                            key.to_owned()
                        } else {
                            format!("{}/{}", prefix, key)
                        };
                        if is_group(value) {
                            walk(value, &path, entries);
                        } else {
                            entries.push((path, value));
                        }
                    }
                }
            }
        }
        let mut entries = Vec::new();
        walk(&self.db, "", &mut entries);
        entries
    }

    /// Collect entry paths in traversal order, excluding groups.
    pub fn paths(&self) -> Vec<String> {
        self.entries().into_iter().map(|(path, _)| path).collect()
    }

    /// Copy entries matching any case-insensitive path-component or keyword term.
    ///
    /// Keyword-only matches are annotated with the first matching keyword.
    pub fn find(&self, names: &[String]) -> Result<Database, String> {
        self.validate()?;
        let names: Vec<_> = names.iter().map(|name| name.to_lowercase()).collect();
        let mut matches = Database {
            path: self.path.clone(),
            db: Yaml::Hash(Default::default()),
            data: None,
        };
        for (path, entry) in self.entries() {
            let path_matches = path_parts(Some(&path))?
                .iter()
                .any(|part| names.iter().any(|term| part.to_lowercase().contains(term)));
            let matched_path = if path_matches {
                Some(path)
            } else {
                let keywords = &entry["keywords"];
                let keywords = match keywords {
                    Yaml::Null | Yaml::BadValue => Vec::new(),
                    Yaml::Array(words) => words.iter().collect(),
                    word => vec![word],
                };
                keywords
                    .iter()
                    .map(|word| scalar_string(word).to_lowercase())
                    .find(|word| names.iter().any(|term| word.contains(term)))
                    .map(|word| format!("{} ({})", path, word))
            };
            if let Some(path) = matched_path {
                matches.put(&path, entry.clone())?;
            }
        }
        sort_node(&mut matches.db)?;
        Ok(matches)
    }

    /// Sort and encrypt the database for a recipient, then atomically replace its file.
    pub fn write_encrypted(&mut self, recipient: &str) -> Result<bool, String> {
        let mut database = self.db.clone();
        sort_node(&mut database)?;
        let yaml = crate::yaml::dump(&database)?;
        if self.data.as_deref() == Some(&yaml) {
            return Ok(false);
        }
        let mut child = Command::new("gpg")
            .args(["--encrypt", "--armor", "--recipient", recipient])
            .stdin(Stdio::piped())
            .stdout(Stdio::piped())
            .stderr(Stdio::piped())
            .spawn()
            .map_err(|e| format!("Executable 'gpg' not found: {}", e))?;
        use std::io::Write;
        let mut stdin = child
            .stdin
            .take()
            .ok_or_else(|| String::from("Couldn't write database to gpg"))?;
        // Drain encrypted output while feeding input; large databases can fill both pipes.
        let (output, written) = std::thread::scope(|scope| {
            let bytes = yaml.as_bytes();
            let writer = scope.spawn(move || stdin.write_all(bytes));
            let output = child.wait_with_output();
            let written = writer
                .join()
                .map_err(|_| String::from("Database writer thread failed"))?;
            Ok::<_, String>((output, written))
        })?;
        let output = output.map_err(|e| format!("Couldn't wait for gpg: {}", e))?;
        if !output.status.success() {
            return Err(format!(
                "gpg encryption failed: {}",
                String::from_utf8_lossy(&output.stderr).trim()
            ));
        }
        written.map_err(|e| format!("Couldn't write database to gpg: {}", e))?;

        let original = Path::new(&self.path);
        let target = if original.is_file() {
            original
                .canonicalize()
                .map_err(|error| format!("Couldn't resolve database path: {}", error))?
        } else {
            original.to_path_buf()
        };
        let path = target.as_path();
        let parent = path.parent().unwrap_or_else(|| Path::new("."));
        let filename = path
            .file_name()
            .ok_or_else(|| String::from("Invalid database path"))?
            .to_string_lossy();
        let nonce = std::time::SystemTime::now()
            .duration_since(std::time::UNIX_EPOCH)
            .map_err(|e| e.to_string())?
            .as_nanos();
        let temp_path: PathBuf = parent.join(format!(".{}.{}.tmp", filename, nonce));
        let mut temp = create_private_file(&temp_path)
            .map_err(|e| format!("Couldn't create temporary database file: {}", e))?;
        let replaced = temp
            .write_all(&output.stdout)
            .map_err(|e| format!("Couldn't write encrypted database: {}", e))
            .and_then(|()| {
                temp.sync_all()
                    .map_err(|e| format!("Couldn't sync encrypted database: {}", e))
            })
            .and_then(|()| {
                std::fs::rename(&temp_path, path)
                    .map_err(|e| format!("Couldn't replace database: {}", e))
            });
        if replaced.is_err() {
            let _ = std::fs::remove_file(&temp_path);
        }
        replaced?;
        self.db = database;
        self.data = Some(yaml);
        Ok(true)
    }

    /// Resolve a slash-separated path, returning the root when no name is supplied.
    pub fn get(&self, name: Option<&str>) -> Result<&Yaml, String> {
        self.get_optional(name)?
            .ok_or_else(|| format!("{} not found", name.unwrap_or_default()))
    }

    /// Look up a node, distinguishing missing nodes from invalid paths.
    pub fn get_optional(&self, name: Option<&str>) -> Result<Option<&Yaml>, String> {
        let mut current = &self.db;
        for part in path_parts(name)? {
            let Some(child) = current.as_hash().and_then(|map| map.get(&map_key(part))) else {
                return Ok(None);
            };
            current = child;
        }
        Ok(Some(current))
    }

    /// Resolve a path's parent mapping, creating missing groups, and return it with the leaf key.
    fn parent_map_mut(&mut self, name: &str) -> Result<(&mut yaml_rust::yaml::Hash, Yaml), String> {
        let parts = path_parts(Some(name))?;
        let (leaf, parents) = parts
            .split_last()
            .ok_or_else(|| String::from("Invalid path"))?;
        match parent_group_mut(&mut self.db, parents)? {
            Yaml::Hash(map) => Ok((map, map_key(leaf))),
            _ => Err(String::from("Invalid database format")),
        }
    }

    /// Insert a node, creating parent groups without traversing entry fields.
    pub fn put(&mut self, name: &str, node: Yaml) -> Result<(), String> {
        let (map, leaf) = self.parent_map_mut(name)?;
        map.insert(leaf, node);
        Ok(())
    }

    /// Remove a node and prune every empty ancestor group.
    pub fn pop(&mut self, name: &str) -> Result<Yaml, String> {
        fn remove(node: &mut Yaml, parts: &[&str]) -> Option<Yaml> {
            let (first, rest) = parts.split_first()?;
            let map = match node {
                Yaml::Hash(map) => map,
                _ => return None,
            };
            let key = map_key(first);
            if rest.is_empty() {
                return map.remove(&key);
            }
            let child = map.get_mut(&key)?;
            let removed = remove(child, rest)?;
            if child.as_hash().is_some_and(|map| map.is_empty()) {
                map.remove(&key);
            }
            Some(removed)
        }
        let parts = path_parts(Some(name))?;
        if parts.is_empty() {
            return Err(String::from("Cannot move the whole database"));
        }
        remove(&mut self.db, &parts).ok_or_else(|| format!("{} not found", name))
    }

    /// List a group's immediate children with a flag identifying each child group.
    ///
    /// Reject paths that select entries instead of groups.
    pub fn group_items(&self, name: Option<&str>) -> Result<Vec<(String, bool)>, String> {
        let label = name.unwrap_or_default().trim_end_matches('/');
        let node = self
            .get_optional(name)?
            .ok_or_else(|| format!("{} not found", label))?;
        if is_entry(node) {
            return Err(format!("{} is an entry, not a group", label));
        }
        let map = node
            .as_hash()
            .ok_or_else(|| format!("{} not found", label))?;
        Ok(map
            .iter()
            .filter_map(|(key, value)| key.as_str().map(|key| (key.to_owned(), is_group(value))))
            .collect())
    }

    /// Set an entry's password, creating parents and preserving other entry fields.
    ///
    /// Return the previous password and save it in `old_password` when present.
    pub fn insert_password(
        &mut self,
        name: &str,
        password: &str,
    ) -> Result<Option<String>, String> {
        let (parent, leaf) = self.parent_map_mut(name)?;
        let entry = parent
            .entry(leaf)
            .or_insert_with(|| Yaml::Hash(Default::default()));
        let Yaml::Hash(entry_map) = entry else {
            return Err(format!("{} is not an entry", name));
        };
        if !entry_map.is_empty() && entry_map.values().all(|v| matches!(v, Yaml::Hash(_))) {
            return Err(format!("{} is a group", name));
        }
        let old_password = entry_map.get(&map_key("password")).map(scalar_string);
        if let Some(old) = &old_password {
            entry_map.insert(map_key("old_password"), Yaml::String(old.clone()));
        }
        entry_map.insert(map_key("password"), Yaml::String(password.to_owned()));
        Ok(old_password)
    }

    /// Check that groups contain mappings and entries do not mix mappings with fields.
    pub(crate) fn validate(&self) -> Result<(), String> {
        /// Validate a group's descendants, retaining their paths for error messages.
        fn validate_group(node: &Yaml, path: &str) -> Result<(), String> {
            let map = node
                .as_hash()
                .ok_or_else(|| String::from("Database is not a dict"))?;
            for (key, value) in map {
                let key = key
                    .as_str()
                    .ok_or_else(|| String::from("Database contains a non-string key"))?;
                let current = if path.is_empty() {
                    key.to_owned()
                } else {
                    format!("{}/{}", path, key)
                };
                let entry = value
                    .as_hash()
                    .ok_or_else(|| format!("'{}' is not a dict", current))?;
                if is_entry(value) {
                    if entry.values().any(|field| matches!(field, Yaml::Hash(_))) {
                        return Err(format!(
                            "Entry '{}' has mixed dict/non-dict values",
                            current
                        ));
                    }
                } else {
                    validate_group(value, &current)?;
                }
            }
            Ok(())
        }
        validate_group(&self.db, "")
    }
}

/// Recursively sort groups before entries and names alphabetically within each class.
fn sort_node(node: &mut Yaml) -> Result<(), String> {
    let map = match node {
        Yaml::Hash(map) => map,
        _ => return Err(String::from("Invalid database format")),
    };
    let mut entries = Vec::with_capacity(map.len());
    for (key, mut value) in std::mem::take(map) {
        let group = is_group(&value);
        if group {
            sort_node(&mut value)?;
        }
        entries.push((!group, key, value));
    }
    entries.sort_by(|(left_entry, left_key, _), (right_entry, right_key, _)| {
        (left_entry, left_key.as_str()).cmp(&(right_entry, right_key.as_str()))
    });
    map.extend(entries.into_iter().map(|(_, key, value)| (key, value)));
    Ok(())
}

/// Read an entry's password, rejecting missing or null values.
pub(crate) fn entry_password(entry: &Yaml, name: &str) -> Result<String, String> {
    match &entry["password"] {
        Yaml::Null | Yaml::BadValue => Err(format!("{} does not have a password", name)),
        password => Ok(scalar_string(password)),
    }
}

/// Identify mappings that contain no entry fields, including empty mappings.
pub fn is_group(value: &Yaml) -> bool {
    matches!(value, Yaml::Hash(_)) && !is_entry(value)
}

impl Display for Database {
    /// Format a database label containing its backing file path.
    fn fmt(&self, f: &mut Formatter<'_>) -> fmt::Result {
        write!(f, "Database: {}", self.path)
    }
}

#[cfg(test)]
#[path = "../tests/unit/database.rs"]
mod tests;
