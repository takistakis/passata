use super::move_paths;
use crate::database::Database;
use yaml_rust::{Yaml, YamlLoader};

fn fixture() -> Database {
    Database {
        path: String::from("/unused"),
        data: None,
        db: YamlLoader::load_from_str(
            "internet:\n  github:\n    password: gh\n    username: takis\n  social:\n    reddit:\n      password: rdt\n      username: sakis\n      keywords: [one, two]\n    twitter:\n      password: twt\nempty: {}\n",
        )
        .unwrap()
        .remove(0),
    }
}

fn run(db: &mut Database, sources: &[&str], dest: &str) -> Result<bool, String> {
    move_paths(
        db,
        &sources
            .iter()
            .map(|name| name.to_string())
            .collect::<Vec<_>>(),
        dest,
        true,
        |_, force| {
            assert!(force);
            Ok(true)
        },
    )
}

#[test]
fn renames_entries_and_preserves_all_fields() {
    for dest in ["renamed", "new/nested/renamed", "internet/reddit"] {
        let mut db = fixture();
        let entry = db.get(Some("internet/social/reddit")).unwrap().clone();
        assert_eq!(run(&mut db, &["internet/social/reddit"], dest), Ok(true));
        assert_eq!(db.get(Some(dest)), Ok(&entry));
        assert!(db.get(Some("internet/social/reddit")).is_err());
        assert!(db.get(Some("internet/social/twitter")).is_ok());
    }
}

#[test]
fn moves_entries_into_existing_new_empty_and_root_groups() {
    for (dest, newname) in [
        ("internet/social", "internet/social/github"),
        ("new/nested/", "new/nested/github"),
        ("empty", "empty/github"),
        ("/", "github"),
    ] {
        let mut db = fixture();
        let entry = db.get(Some("internet/github")).unwrap().clone();
        assert_eq!(run(&mut db, &["internet/github/"], dest), Ok(true));
        assert_eq!(db.get(Some(newname)), Ok(&entry));
        assert!(db.get(Some("internet/github")).is_err());
    }
}

#[test]
fn moves_multiple_entries_and_prunes_empty_ancestors() {
    for dest in ["new/", "/"] {
        let mut db = fixture();
        assert_eq!(
            run(
                &mut db,
                &["internet/social/reddit", "internet/social/twitter"],
                dest,
            ),
            Ok(true)
        );
        let prefix = if dest == "/" { "" } else { "new/" };
        assert_eq!(
            db.get(Some(&format!("{}reddit", prefix))).unwrap()["password"],
            Yaml::String("rdt".into())
        );
        assert!(db.get(Some(&format!("{}twitter", prefix))).is_ok());
        assert!(db.get(Some("internet/social")).is_err());
        assert!(db.get(Some("internet/github")).is_ok());
    }
    let mut db = fixture();
    run(&mut db, &["internet"], "renamed/nested/").unwrap();
    assert!(db.get(Some("internet")).is_err());
    assert!(db.get(Some("renamed/nested/social/reddit")).is_ok());
}

#[test]
fn overwrite_confirmation_and_force_preserve_source_fields() {
    let mut db = fixture();
    let original = db.db.clone();
    let sources = vec!["internet/social/reddit".to_owned()];
    assert_eq!(
        move_paths(
            &mut db,
            &sources,
            "internet/github",
            false,
            |message, force| {
                assert_eq!(message, "Overwrite internet/github?");
                assert!(!force);
                Ok(false)
            }
        ),
        Ok(false)
    );
    assert_eq!(db.db, original);
    let source = db.get(Some(&sources[0])).unwrap().clone();
    run(&mut db, &[&sources[0]], "internet/github").unwrap();
    assert_eq!(db.get(Some("internet/github")), Ok(&source));
    assert!(db.get(Some(&sources[0])).is_err());
}

#[test]
fn errors_and_late_cancellation_are_atomic() {
    for (sources, dest, error) in [
        (vec!["missing"], "new", "missing not found"),
        (
            vec!["internet/github", "missing"],
            "new/",
            "missing not found",
        ),
        (
            vec!["internet/github", "internet/social/reddit"],
            "new",
            "new is not a group",
        ),
        (
            vec!["internet"],
            "internet/github",
            "internet/github already exists",
        ),
        (vec!["internet"], "empty/", "empty already exists"),
        (
            vec!["internet"],
            "internet/social/deep",
            "Cannot move 'internet' into its own subdirectory",
        ),
        (
            vec!["internet/social/reddit"],
            "internet/github/child",
            "'github' is an entry, cannot create subpath",
        ),
        (vec!["/"], "new", "Cannot move the whole database"),
        (
            vec!["internet/github/password"],
            "new",
            "internet/github/password is not an entry or group",
        ),
        (vec!["internet/github"], "/new", "Invalid path: /new"),
        (
            vec!["internet/github"],
            "new//child",
            "Invalid path: new//child",
        ),
    ] {
        let mut db = fixture();
        let original = db.db.clone();
        assert_eq!(run(&mut db, &sources, dest), Err(error.to_owned()));
        assert_eq!(db.db, original);
    }

    let mut db = fixture();
    let original = db.db.clone();
    let sources = vec![
        "internet/social/reddit".to_owned(),
        "internet/github".to_owned(),
    ];
    assert_eq!(
        move_paths(&mut db, &sources, "internet", false, |_, _| Ok(false)),
        Ok(false)
    );
    assert_eq!(db.db, original);
}

#[test]
fn moves_groups_in_multiple_source_mode_and_keeps_empty_groups() {
    let mut db = fixture();
    run(&mut db, &["internet/social", "internet/github"], "new/").unwrap();
    assert!(db.get(Some("new/social/reddit")).is_ok());
    assert!(db.get(Some("new/github")).is_ok());
    assert!(db.get(Some("internet")).is_err());
    run(&mut db, &["empty"], "renamed").unwrap();
    assert!(
        db.get(Some("renamed"))
            .unwrap()
            .as_hash()
            .unwrap()
            .is_empty()
    );
    assert!(db.get(Some("empty")).is_err());
}

#[test]
fn moving_an_entry_to_itself_does_not_lose_it() {
    let mut db = fixture();
    let original = db.db.clone();
    run(&mut db, &["internet/github"], "internet/github").unwrap();
    assert_eq!(
        db.get(Some("internet/github")),
        Ok(&original["internet"]["github"])
    );
}
