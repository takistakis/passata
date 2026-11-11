use super::format_items;

#[test]
/// Verify newline-separated group and entry names without ANSI styling.
fn formats_groups_and_entries_without_color() {
    let items = vec![
        (String::from("accounts"), true),
        (String::from("mail"), false),
    ];
    assert_eq!(format_items(&items, false), "accounts\nmail");
}

#[test]
/// Verify that only groups receive styling and empty listings produce no text.
fn colors_only_groups_when_requested() {
    let items = vec![
        (String::from("accounts"), true),
        (String::from("mail"), false),
    ];
    let output = format_items(&items, true);
    assert!(output.starts_with("\x1b["));
    assert!(output.ends_with("\nmail"));
    assert_eq!(format_items(&[], true), "");
}
