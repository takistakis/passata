use yaml_rust::YamlLoader;

use crate::database::Database;

const YAML: &str = "
internet:
  reddit:
    password: rdt
    username: sakis
  empty-password:
    username: user
";

fn database() -> Database {
    Database {
        path: String::from("/tmp/test"),
        db: YamlLoader::load_from_str(YAML).unwrap().remove(0),
        data: None,
    }
}

#[test]
fn inserts_new_entry_and_preserves_other_fields() {
    let mut db = database();
    assert!(
        super::insert_into_database(&mut db, "internet/new", "secret", false, |_, _| {
            panic!("new entries do not need confirmation")
        })
        .unwrap()
    );
    assert_eq!(
        db.get(Some("internet/new/password")).unwrap().as_str(),
        Some("secret")
    );
}

#[test]
fn overwrites_password_after_confirmation_and_keeps_backup() {
    let mut db = database();
    let mut prompted = false;
    assert!(
        super::insert_into_database(
            &mut db,
            "internet/reddit",
            "new",
            false,
            |message, force| {
                prompted = true;
                assert_eq!(message, "Overwrite internet/reddit?");
                assert!(!force);
                Ok(true)
            }
        )
        .unwrap()
    );
    assert!(prompted);
    let entry = db.get(Some("internet/reddit")).unwrap();
    assert_eq!(entry["password"].as_str(), Some("new"));
    assert_eq!(entry["old_password"].as_str(), Some("rdt"));
    assert_eq!(entry["username"].as_str(), Some("sakis"));
}

#[test]
fn declined_overwrite_leaves_database_unchanged() {
    let mut db = database();
    assert!(
        !super::insert_into_database(&mut db, "internet/reddit", "new", false, |_, _| {
            Ok(false)
        })
        .unwrap()
    );
    assert_eq!(
        db.get(Some("internet/reddit/password")).unwrap().as_str(),
        Some("rdt")
    );
    assert!(
        db.get_optional(Some("internet/reddit/old_password"))
            .unwrap()
            .is_none()
    );
}

#[test]
fn does_not_confirm_or_backup_when_entry_has_no_password() {
    let mut db = database();
    assert!(
        super::insert_into_database(&mut db, "internet/empty-password", "new", false, |_, _| {
            panic!("entry without a password does not need confirmation")
        })
        .unwrap()
    );
    let entry = db.get(Some("internet/empty-password")).unwrap();
    assert_eq!(entry["password"].as_str(), Some("new"));
    assert!(entry["old_password"].is_badvalue());
    assert_eq!(entry["username"].as_str(), Some("user"));
}

#[test]
fn rejects_groups() {
    let mut db = database();
    assert_eq!(
        super::insert_into_database(&mut db, "internet", "new", true, |_, _| Ok(true)),
        Err(String::from("internet is a group"))
    );
}
