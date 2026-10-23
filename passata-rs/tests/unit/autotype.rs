use std::time::Duration;

use super::{Action, choose_entry, key_names, match_entries, parse_actions, sequence_keys};
use crate::database::Database;
use yaml_rust::{Yaml, YamlLoader};

fn yaml(source: &str) -> Yaml {
    YamlLoader::load_from_str(source).unwrap().remove(0)
}

fn strings(items: &[&str]) -> Vec<String> {
    items.iter().map(|item| item.to_string()).collect()
}

#[test]
/// Verify title matching on entry names and keywords, case-insensitively.
fn matches_window_title_against_names_and_keywords() {
    let db = Database {
        path: String::new(),
        data: None,
        db: yaml(
            "internet:\n  github:\n    password: gh\n  google:\n    password: pw\n    keywords:\n    - YouTube\n    - gmail\nserver:\n  password: srv\n",
        ),
    };
    let (names, matches) = match_entries(&db, "Watch - YOUTUBE - Mozilla Firefox");
    assert_eq!(names, strings(&["internet/github", "internet/google", "server"]));
    assert_eq!(matches, strings(&["internet/google"]));
    assert!(match_entries(&db, "Terminal").1.is_empty());
}

#[test]
/// Verify the default sequences, explicit sequences, and missing credentials.
fn chooses_default_sequence_from_fields() {
    let keys = |source| sequence_keys(&yaml(source));
    assert_eq!(
        keys("username: u\npassword: p").unwrap(),
        strings(&["<username>", "Tab", "<password>", "Return"])
    );
    assert_eq!(keys("username: ''\npassword: p").unwrap(), strings(&["<password>", "Return"]));
    assert_eq!(
        keys("password: p\nautotype: <password>  !1.5 Return").unwrap(),
        strings(&["<password>", "!1.5", "Return"])
    );
    assert_eq!(keys("username: u").unwrap_err(), "Don't know what to type :(");
}

#[test]
/// Verify field substitution, sleeps, keys, and errors for empty fields or bad durations.
fn resolves_sequence_actions() {
    let entry = yaml("username: user\npassword: 1234\nempty: ''");
    assert_eq!(
        parse_actions(&strings(&["<username>", "!0.5", "ctrl+a", "<password>"]), &entry).unwrap(),
        vec![
            Action::Text(String::from("user")),
            Action::Sleep(Duration::from_millis(500)),
            Action::Key(String::from("ctrl+a")),
            Action::Text(String::from("1234")),
        ]
    );
    assert_eq!(parse_actions(&strings(&["<empty>"]), &entry).unwrap_err(), "empty not found");
    assert_eq!(parse_actions(&strings(&["<missing>"]), &entry).unwrap_err(), "missing not found");
    assert_eq!(
        parse_actions(&strings(&["!-1"]), &entry).unwrap_err(),
        "Invalid sleep duration: !-1"
    );
}

#[test]
/// Verify xdotool-style key combinations and modifier aliases.
fn splits_key_combinations() {
    assert_eq!(key_names("Return"), Some(vec!["Return"]));
    assert_eq!(key_names("ctrl+alt+Delete"), Some(vec!["Control_L", "Alt_L", "Delete"]));
    assert_eq!(key_names("Super+shift+a"), Some(vec!["Super_L", "Shift_L", "a"]));
    assert_eq!(key_names("ctrl++"), Some(vec!["Control_L", "plus"]));
    assert_eq!(key_names("+"), Some(vec!["plus"]));
    assert_eq!(key_names("ctrl+"), None);
    assert_eq!(key_names("ctrl++a"), None);
}

#[cfg(target_os = "linux")]
#[test]
/// Verify keysym resolution through libxkbcommon, including the case-insensitive fallback.
fn resolves_keysyms() {
    use super::backend::parse_key;
    assert_eq!(parse_key("ctrl+Return").unwrap(), vec![0xffe3, 0xff0d]);
    assert_eq!(parse_key("tab").unwrap(), vec![0xff09]);
    assert_eq!(parse_key("NoSuchKey").unwrap_err(), "Invalid key: NoSuchKey");
}

#[test]
/// Verify a single match skips the menu and that the menu receives sorted candidates.
fn chooses_entry_with_menu() {
    let names = strings(&["b", "a", "c"]);
    let menu = strings(&["head", "-n1"]);
    assert_eq!(choose_entry(&names, &strings(&["c"]), &strings(&["false"])).unwrap(), "c");
    assert_eq!(choose_entry(&names, &[], &menu).unwrap(), "a");
    assert_eq!(choose_entry(&names, &strings(&["c", "b"]), &menu).unwrap(), "b");
    assert_eq!(choose_entry(&[], &[], &menu).unwrap_err(), "No entries to autotype");
    assert!(
        choose_entry(&names, &[], &strings(&["false"]))
            .unwrap_err()
            .starts_with("Command 'false' returned non-zero exit status 1.")
    );
}
