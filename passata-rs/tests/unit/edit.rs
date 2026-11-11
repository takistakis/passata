use yaml_rust::{Yaml, YamlLoader};

use super::{apply_edit, final_content_is_unsaved, parse_edit_yaml};
use crate::cli;
use crate::database::Database;

fn database(contents: &str) -> Database {
    Database {
        path: String::from("/unused"),
        data: None,
        db: YamlLoader::load_from_str(contents).unwrap().remove(0),
    }
}

#[test]
fn parses_empty_yaml_and_rejects_invalid_documents() {
    assert_eq!(parse_edit_yaml("").unwrap(), Yaml::Hash(Default::default()));
    assert!(parse_edit_yaml("[invalid").is_err());
    assert!(parse_edit_yaml("- item\n").is_err());
    assert!(parse_edit_yaml("---\na: 1\n---\nb: 2\n").is_err());
}

#[test]
fn final_reconciliation_detects_a_revert_after_a_live_save() {
    let original = "# entry\npassword: old\n";
    let live_edit = "# entry\npassword: new\n";
    assert!(!final_content_is_unsaved(original, original));
    assert!(final_content_is_unsaved(live_edit, original));
}

#[test]
fn replaces_selected_nodes_and_removes_empty_nodes() {
    let mut db = database("group:\n  entry:\n    password: old\n");
    let replacement = parse_edit_yaml("password: new\nusername: user\n").unwrap();
    apply_edit(&mut db, Some("group/entry"), replacement).unwrap();
    assert_eq!(
        db.get(Some("group/entry")).unwrap()["password"].as_str(),
        Some("new")
    );

    apply_edit(&mut db, Some("group/entry"), Yaml::Hash(Default::default())).unwrap();
    assert!(db.get_optional(Some("group")).unwrap().is_none());
}

#[test]
fn replaces_or_clears_the_complete_database() {
    let mut db = database("old:\n  password: value\n");
    apply_edit(&mut db, None, parse_edit_yaml("new: {}\n").unwrap()).unwrap();
    assert!(db.get_optional(Some("old")).unwrap().is_none());
    assert!(db.get_optional(Some("new")).unwrap().is_some());

    apply_edit(&mut db, None, Yaml::Hash(Default::default())).unwrap();
    assert!(db.db.as_hash().unwrap().is_empty());

    apply_edit(&mut db, Some("/"), parse_edit_yaml("root: {}\n").unwrap()).unwrap();
    assert!(db.get_optional(Some("root")).unwrap().is_some());
}

#[test]
fn cli_parses_optional_name_and_editor_command() {
    let matches = cli()
        .try_get_matches_from(["passata", "edit", "group/entry", "--editor", "vim -f"])
        .unwrap();
    let args = matches.subcommand_matches("edit").unwrap();
    assert_eq!(
        args.get_one::<String>("name").map(String::as_str),
        Some("group/entry")
    );
    assert_eq!(
        args.get_one::<String>("editor").map(String::as_str),
        Some("vim -f")
    );
    assert!(
        cli()
            .try_get_matches_from(["passata", "edit"])
            .unwrap()
            .subcommand_matches("edit")
            .unwrap()
            .get_one::<String>("name")
            .is_none()
    );
}
