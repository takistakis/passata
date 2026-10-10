use super::remove_paths;
use crate::database::Database;
use yaml_rust::{Yaml, YamlLoader};

fn fixture() -> Database {
    Database {
        path: String::from("/unused"),
        data: None,
        db: YamlLoader::load_from_str(
            "internet:\n  github:\n    password: gh\n  social:\n    reddit:\n      password: rdt\nempty: {}\n",
        )
        .unwrap()
        .remove(0),
    }
}

fn run(db: &mut Database, names: &[&str], force: bool, recursive: bool) -> Result<bool, String> {
    remove_paths(
        db,
        &names
            .iter()
            .map(|name| name.to_string())
            .collect::<Vec<_>>(),
        force,
        recursive,
        |_, force| {
            assert!(force);
            Ok(true)
        },
    )
}

#[test]
fn removes_entries_and_prunes_empty_ancestor_groups() {
    let mut db = fixture();
    assert_eq!(
        run(&mut db, &["internet/social/reddit"], true, false),
        Ok(true)
    );
    assert!(db.get(Some("internet/social")).is_err());
    assert!(db.get(Some("internet/github")).is_ok());
}

#[test]
fn recursively_removes_groups_and_empty_groups() {
    for name in ["internet/social", "empty"] {
        let mut db = fixture();
        assert_eq!(run(&mut db, &[name], true, true), Ok(true));
        assert!(db.get(Some(name)).is_err());
    }
}

#[test]
fn requires_recursive_for_groups_and_clears_the_root_only_with_recursive() {
    let mut db = fixture();
    let original = db.db.clone();
    assert_eq!(
        run(&mut db, &["internet"], true, false),
        Err(String::from(
            "Cannot remove 'internet': is a group, use -r to remove"
        ))
    );
    assert_eq!(db.db, original);
    assert_eq!(run(&mut db, &["/"], true, true), Ok(true));
    assert_eq!(db.db, Yaml::Hash(Default::default()));

    let mut empty = Database {
        path: String::from("/unused"),
        data: None,
        db: Yaml::Hash(Default::default()),
    };
    assert_eq!(
        run(&mut empty, &["/"], true, false),
        Err("Cannot remove '/': is a group, use -r to remove".into())
    );
}

#[test]
fn confirms_once_for_multiple_names_and_does_not_apply_partial_changes() {
    let mut db = fixture();
    let original = db.db.clone();
    let names = vec!["internet/github".to_owned(), "missing".to_owned()];
    assert_eq!(
        remove_paths(&mut db, &names, false, false, |message, force| {
            if force {
                Ok(true)
            } else {
                assert_eq!(message, "Delete 2 arguments?");
                Ok(true)
            }
        }),
        Err(String::from("missing not found"))
    );
    assert_eq!(db.db, original);

    assert_eq!(
        remove_paths(&mut db, &names, false, false, |_, _| Ok(false)),
        Ok(false)
    );
    assert_eq!(db.db, original);
}

#[test]
fn single_item_confirmation_decline_and_invalid_paths_preserve_database() {
    let mut db = fixture();
    let original = db.db.clone();
    assert_eq!(
        remove_paths(
            &mut db,
            &["internet/github".into()],
            false,
            false,
            |message, force| {
                assert_eq!(message, "Delete 'internet/github'?");
                assert!(!force);
                Ok(false)
            }
        ),
        Ok(false)
    );
    assert_eq!(db.db, original);
    assert_eq!(
        run(&mut db, &["internet//github"], true, false),
        Err(String::from("Invalid path: internet//github"))
    );
    assert_eq!(db.db, original);
}
