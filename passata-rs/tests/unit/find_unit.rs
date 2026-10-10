use super::{first_password, render_matches};
use crate::database::Database;
use yaml_rust::YamlLoader;

/// Build an in-memory search fixture with nested groups, passwords, and keywords.
fn database() -> Database {
    Database {
        path: String::new(),
        data: None,
        db: YamlLoader::load_from_str(
            "internet:\n  github:\n    password: gh\n  reddit:\n    password: rdt\n    username: sakis\n  social:\n    twitter:\n      password: twt\nserver:\n  password: srv\nmail:\n  google:\n    username: user\n    keywords:\n    - YouTube\n    - Gmail\n",
        )
        .unwrap()
        .remove(0),
    }
}

/// Search the shared fixture using borrowed terms converted to owned strings.
fn search(names: &[&str]) -> Database {
    database()
        .find(
            &names
                .iter()
                .map(|name| name.to_string())
                .collect::<Vec<_>>(),
        )
        .unwrap()
}

#[test]
/// Verify case-insensitive any-term matching, result rendering, and first-password selection.
fn matches_paths_case_insensitively_with_any_term() {
    let matches = search(&["RED", "git"]);
    assert_eq!(matches.paths(), vec!["internet/github", "internet/reddit"]);
    assert_eq!(
        render_matches(&matches, false, false, false).unwrap(),
        ".\n└── internet\n    ├── github\n    └── reddit"
    );
    assert_eq!(
        render_matches(&matches, false, true, false).unwrap(),
        "internet/github\ninternet/reddit"
    );
    assert_eq!(
        first_password(&matches).unwrap(),
        Some(("internet/github".into(), "gh".into()))
    );
}

#[test]
/// Verify that group terms select descendants and top-level entries remain searchable.
fn matches_groups_and_top_level_entries() {
    assert_eq!(search(&["social"]).paths(), vec!["internet/social/twitter"]);
    assert_eq!(search(&["server"]).paths(), vec!["server"]);
    assert_eq!(
        search(&["internet"]).paths(),
        vec![
            "internet/github",
            "internet/reddit",
            "internet/social/twitter"
        ]
    );
}

#[test]
/// Verify that keyword-only matches use the first matching keyword as an annotation.
fn keyword_matches_are_annotated_with_the_first_matching_keyword() {
    assert_eq!(search(&["MAIL"]).paths(), vec!["mail/google"]);
    assert_eq!(
        search(&["tube", "gmail"]).paths(),
        vec!["mail/google (youtube)"]
    );
    let matches = search(&["tube"]);
    assert_eq!(
        render_matches(&matches, false, false, false).unwrap(),
        ".\n└── mail\n    └── google (youtube)"
    );
    assert_eq!(
        first_password(&matches).unwrap_err(),
        "mail/google (youtube) does not have a password"
    );
}

#[test]
/// Verify that YAML output overrides path output and retains all entry fields.
fn printing_takes_precedence_over_paths_and_preserves_entry_fields() {
    assert_eq!(
        render_matches(&search(&["red"]), true, true, false).unwrap(),
        "internet:\n  reddit:\n    password: rdt\n    username: sakis"
    );
}

#[test]
/// Verify that absent terms or unmatched terms produce no paths, tree, or first password.
fn empty_search_and_no_matches_do_not_render_a_tree() {
    for terms in [&[][..], &["no-such-entry"][..]] {
        let matches = search(terms);
        assert!(matches.paths().is_empty());
        assert_eq!(render_matches(&matches, false, false, false).unwrap(), "");
        assert_eq!(first_password(&matches).unwrap(), None);
    }
}

#[test]
/// Verify that search examines path components rather than combined paths or password values.
fn terms_match_components_not_whole_paths_or_passwords() {
    assert!(search(&["internet/red"]).paths().is_empty());
    assert!(search(&["rdt"]).paths().is_empty());
}

#[test]
/// Verify scalar keyword matching and password conversion without mutating the source database.
fn scalar_keywords_are_supported_and_source_is_unchanged() {
    let db = Database {
        path: String::new(),
        data: None,
        db: YamlLoader::load_from_str("entry:\n  password: 123\n  keywords: EXAMPLE\nempty: {}\n")
            .unwrap()
            .remove(0),
    };
    let original = db.db.clone();
    let matches = db.find(&["example".into()]).unwrap();
    assert_eq!(matches.paths(), vec!["entry (example)"]);
    assert_eq!(
        first_password(&matches).unwrap(),
        Some(("entry (example)".into(), "123".into()))
    );
    assert_eq!(db.db, original);
}

#[test]
/// Verify that slash-containing keyword annotations still allow password lookup.
fn annotated_keywords_with_slashes_remain_resolvable() {
    let db = Database {
        path: String::new(),
        data: None,
        db: YamlLoader::load_from_str("entry:\n  password: secret\n  keywords: example/mail\n")
            .unwrap()
            .remove(0),
    };
    let matches = db.find(&["mail".into()]).unwrap();
    assert_eq!(matches.paths(), vec!["entry (example/mail)"]);
    assert_eq!(
        first_password(&matches).unwrap(),
        Some(("entry (example/mail)".into(), "secret".into()))
    );
}

#[test]
/// Verify that null passwords cannot be selected for clipboard output.
fn null_passwords_are_rejected_for_clipboard() {
    let db = Database {
        path: String::new(),
        data: None,
        db: YamlLoader::load_from_str("entry:\n  password: null\n")
            .unwrap()
            .remove(0),
    };
    assert_eq!(
        first_password(&db).unwrap_err(),
        "entry does not have a password"
    );
}
