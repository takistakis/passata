use super::{colorize, is_group, pager_color, render_children, render_tree};
use yaml_rust::YamlLoader;

#[test]
/// Verify ANSI highlighting of YAML mapping keys and list markers.
fn colorize_marks_mapping_keys_and_list_markers() {
    let output = colorize("username: alice\nitems:\n  - first\n");
    assert!(
        output.contains("\x1b[38;5;12musername\x1b[38;5;11m: \x1b[0malice"),
        "{:?}",
        output
    );
    assert!(output.contains("\x1b[38;5;9m  - \x1b[0mfirst"));
    assert!(output.contains("\x1b[38;5;12mitems\x1b[38;5;11m:\x1b[0m"));
}

#[test]
/// Verify that lines without YAML-style markers remain unchanged.
fn colorize_leaves_plain_lines_untouched() {
    assert_eq!(colorize("plain text\n"), "plain text\n");
}

#[test]
/// Verify connector and indentation output for nested groups and entries.
fn renders_nested_groups_with_python_connectors() {
    let yaml = "
internet:
  social:
    reddit:
      password: rdt
    twitter:
      password: twt
  github:
    password: gh
";
    let mut docs = YamlLoader::load_from_str(yaml).unwrap();
    let doc = docs.remove(0);
    let root = &doc["internet"];
    let mut lines = Vec::new();
    render_children(root, "", false, &mut lines);
    assert_eq!(
        lines,
        vec![
            "├── social",
            "│   ├── reddit",
            "│   └── twitter",
            "└── github"
        ]
    );
}

#[test]
/// Verify classification of empty groups, populated groups, entries, and missing nodes.
fn identifies_empty_and_populated_groups() {
    let mut docs =
        YamlLoader::load_from_str("empty: {}\nentry:\n  password: secret\ngroup:\n  nested: {}\n")
            .unwrap();
    let doc = docs.remove(0);
    assert!(is_group(&doc["empty"]));
    assert!(!is_group(&doc["entry"]));
    assert!(is_group(&doc["group"]));
    assert!(!is_group(&doc["missing"]));
}

#[test]
/// Verify that tree rendering skips non-string keys and does not descend into entry fields.
fn skips_non_string_keys_and_non_group_values() {
    let mut docs =
        YamlLoader::load_from_str("? 1\n: scalar\nentry:\n  password: secret\n").unwrap();
    let doc = docs.remove(0);
    let mut lines = Vec::new();
    render_children(&doc, "", false, &mut lines);
    assert_eq!(lines, vec!["└── entry"]);
}

#[test]
/// Verify that an empty mapping renders without even a root label.
fn renders_empty_tree_as_no_output() {
    assert_eq!(
        render_tree(&YamlLoader::load_from_str("{}").unwrap()[0], ".", false),
        ""
    );
}

#[test]
/// Verify that explicit color settings override pager detection and configured preferences.
fn resolves_pager_color_preferences() {
    let matches = crate::cli()
        .try_get_matches_from(["passata", "ls"])
        .unwrap();
    let args = matches.subcommand_matches("ls").unwrap();
    assert!(!pager_color(args, None, false));
    assert!(pager_color(args, None, true));
    assert!(pager_color(args, Some(true), false));
    assert!(!pager_color(args, Some(false), true));

    let matches = crate::cli()
        .try_get_matches_from(["passata", "--color", "ls"])
        .unwrap();
    assert!(pager_color(
        matches.subcommand_matches("ls").unwrap(),
        Some(false),
        false
    ));
    let matches = crate::cli()
        .try_get_matches_from(["passata", "--no-color", "ls"])
        .unwrap();
    assert!(!pager_color(
        matches.subcommand_matches("ls").unwrap(),
        Some(true),
        true
    ));
}
