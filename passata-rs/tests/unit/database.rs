use std::path::Path;

use yaml_rust::{Yaml, YamlLoader};

use crate::database::Database;

const YAML: &str = "
  group:
    test:
      username: yolo
      password: pass
      keywords:
      - key1
      - key2
";

/// Build the shared nested-entry fixture without decrypting a file.
fn get_db() -> Database {
    let mut docs = YamlLoader::load_from_str(YAML).unwrap();
    Database {
        path: String::from("/tmp/test"),
        data: None,
        db: docs.remove(0),
    }
}

#[test]
/// Verify that nested entry paths resolve successfully.
fn paths_resolve_nested_entries() {
    assert!(get_db().get(Some("group/test")).is_ok());
}

#[test]
/// Verify that a trailing slash still selects the intended group.
fn trailing_slash_selects_group() {
    assert!(get_db().get(Some("group/")).is_ok());
}

#[test]
/// Verify that replacing a password preserves other fields and backs up the old value.
fn insert_preserves_existing_fields_and_backs_up_password() {
    let mut db = get_db();
    assert_eq!(
        db.insert_password("group/test", "new"),
        Ok(Some(String::from("pass")))
    );
    let entry = db.get(Some("group/test")).unwrap().as_hash().unwrap();
    assert_eq!(
        entry.get(&Yaml::String(String::from("password"))),
        Some(&Yaml::String(String::from("new")))
    );
    assert_eq!(
        entry.get(&Yaml::String(String::from("old_password"))),
        Some(&Yaml::String(String::from("pass")))
    );
    assert!(entry.contains_key(&Yaml::String(String::from("username"))));
}

#[test]
/// Verify nested lookup, group listing, and YAML serialization for a deeper hierarchy.
fn nested_entry_paths_are_returned() {
    let mut docs =
        YamlLoader::load_from_str("internet:\n  social:\n    reddit:\n      password: pass\n")
            .unwrap();
    let db = Database {
        path: String::from("/tmp/test"),
        data: None,
        db: docs.remove(0),
    };
    assert!(db.get(Some("internet/social/reddit")).is_ok());
    assert_eq!(db.group_items(Some("internet/")).unwrap()[0].0, "social");
    assert!(db.yaml_for(&db.db).unwrap().contains("reddit:"));
}

#[test]
/// Verify that competing locks fail and dropping the guard permits reacquisition.
fn database_lock_is_exclusive_and_released_on_drop() {
    let path = format!("/tmp/passata-lock-test-{}", std::process::id());
    let lock = super::DatabaseLock::acquire(&path).unwrap();
    assert_eq!(
        super::DatabaseLock::acquire(&path).err(),
        Some(String::from(
            "Another passata process is editing the database"
        ))
    );
    drop(lock);
    let lock = super::DatabaseLock::acquire(&path).unwrap();
    drop(lock);
    std::fs::remove_file(Path::new(&path).with_extension("lock")).unwrap();
}

#[test]
fn unchanged_writes_are_skipped_and_pending_hooks_run_only_once() {
    use std::os::unix::fs::PermissionsExt;

    let directory = std::env::temp_dir().join(format!(
        "passata-hook-unit-{}-{}",
        std::process::id(),
        std::time::SystemTime::now()
            .duration_since(std::time::UNIX_EPOCH)
            .unwrap()
            .as_nanos()
    ));
    std::fs::create_dir_all(directory.join("hooks")).unwrap();
    let hook = directory.join("hooks/post-write");
    std::fs::write(
        &hook,
        "#!/bin/sh\nprintf 'post\\n' >> \"$(dirname \"$0\")/../events\"\n",
    )
    .unwrap();
    std::fs::set_permissions(&hook, std::fs::Permissions::from_mode(0o700)).unwrap();
    let mut hooks = super::DatabaseHooks::new(&directory.join("config.yml"));
    let mut db = get_db();
    db.path = directory
        .join("database.gpg")
        .to_string_lossy()
        .into_owned();
    super::sort_node(&mut db.db).unwrap();
    db.data = Some(db.yaml_for(&db.db).unwrap());
    hooks.write(&mut db, "unused-recipient").unwrap();
    assert!(!Path::new(&db.path).exists());
    hooks.finish().unwrap();
    assert!(!directory.join("events").exists());

    hooks.written = true;
    hooks.write(&mut db, "unused-recipient").unwrap();
    db.db = Yaml::BadValue;
    assert!(hooks.write(&mut db, "unused-recipient").is_err());
    hooks.finish().unwrap();
    hooks.finish().unwrap();
    assert_eq!(
        std::fs::read_to_string(directory.join("events")).unwrap(),
        "post\n"
    );
    std::fs::remove_file(hook).unwrap();
    std::fs::remove_file(directory.join("events")).unwrap();
    std::fs::remove_dir(directory.join("hooks")).unwrap();
    std::fs::remove_dir(directory).unwrap();
}

#[test]
/// Verify that group listings identify child types and reject entries or missing paths.
fn group_items_distinguishes_groups_and_entries() {
    let db = get_db();
    assert_eq!(
        db.group_items(None).unwrap(),
        vec![(String::from("group"), true)]
    );
    assert_eq!(
        db.group_items(Some("group")).unwrap(),
        vec![(String::from("test"), false)]
    );
    assert_eq!(
        db.group_items(Some("group/test")),
        Err(String::from("group/test is an entry, not a group"))
    );
    assert_eq!(
        db.group_items(Some("missing/")),
        Err(String::from("missing not found"))
    );
}

#[test]
/// Verify creation of parent groups and rejection of group, entry, and malformed-path conflicts.
fn insertion_creates_nested_groups_and_rejects_conflicts() {
    let mut docs = YamlLoader::load_from_str("{}").unwrap();
    let mut db = Database {
        path: String::from("/tmp/test"),
        data: None,
        db: docs.remove(0),
    };
    assert_eq!(db.insert_password("new/group/entry", "secret"), Ok(None));
    assert_eq!(
        db.get(Some("new/group/entry/password")).unwrap().as_str(),
        Some("secret")
    );
    assert_eq!(
        db.insert_password("new", "secret"),
        Err(String::from("new is a group"))
    );

    assert_eq!(
        db.insert_password("new/group/entry/child", "secret"),
        Err(String::from("'entry' is an entry, cannot create subpath"))
    );
    assert_eq!(
        db.insert_password("new//invalid", "secret"),
        Err(String::from("Invalid path: new//invalid"))
    );
}

#[test]
/// Verify validation errors for non-mapping nodes, non-string keys, and mixed entry fields.
fn validation_rejects_invalid_database_shapes() {
    let invalid_databases = [
        ("- scalar\n", "Database is not a dict"),
        ("entry: scalar\n", "'entry' is not a dict"),
        ("? 1\n: {}\n", "Database contains a non-string key"),
        (
            "entry:\n  password: secret\n  metadata:\n    nested: value\n",
            "Entry 'entry' has mixed dict/non-dict values",
        ),
    ];
    for (yaml, expected_error) in invalid_databases {
        let mut docs = YamlLoader::load_from_str(yaml).unwrap();
        let db = Database {
            path: String::from("/tmp/test"),
            data: None,
            db: docs.remove(0),
        };
        assert_eq!(db.validate().unwrap_err(), expected_error, "{yaml}");
    }
}

#[test]
/// Verify group-first alphabetical sorting and rejection of non-mapping roots.
fn sorting_places_groups_before_entries_and_sorts_each_level() {
    let mut docs = YamlLoader::load_from_str(
        "z_entry:\n  password: z\nb_group:\n  z_entry:\n    password: z\na_group:\n  a_entry:\n    password: a\na_entry:\n  password: a\n",
    )
    .unwrap();
    let mut db = docs.remove(0);
    super::sort_node(&mut db).unwrap();
    let keys: Vec<_> = db
        .as_hash()
        .unwrap()
        .keys()
        .map(|key| key.as_str().unwrap())
        .collect();
    assert_eq!(keys, vec!["a_group", "b_group", "a_entry", "z_entry"]);
    let nested_keys: Vec<_> = db["a_group"]
        .as_hash()
        .unwrap()
        .keys()
        .map(|key| key.as_str().unwrap())
        .collect();
    assert_eq!(nested_keys, vec!["a_entry"]);
    assert_eq!(
        super::sort_node(&mut Yaml::String("not a map".into())),
        Err(String::from("Invalid database format"))
    );
}

#[test]
/// Verify that the display representation identifies the database file.
fn database_display_includes_its_path() {
    assert_eq!(get_db().to_string(), "Database: /tmp/test");
}
