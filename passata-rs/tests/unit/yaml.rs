use super::dump;
use yaml_rust::{Yaml, YamlLoader};

fn mapping(value: &str) -> Yaml {
    let mut map = yaml_rust::yaml::Hash::new();
    map.insert(Yaml::String("password".into()), Yaml::String(value.into()));
    Yaml::Hash(map)
}

#[test]
fn plain_strings_match_pyyaml() {
    for value in [
        "secret",
        "p@ss#word",
        "https://example.com:8080/login",
        "abc:def",
        "a,b",
        "a[b]{c}",
        "a`b",
        "it's fine",
        "say \"hello\"",
        r"C:\Users\name",
        "-secret",
        "?secret",
        ":secret",
        ".hidden",
        "<username> Tab <password> Return",
        "Ελληνικά",
        "🔑",
    ] {
        let node = mapping(value);
        let output = dump(&node).unwrap();
        assert_eq!(output, format!("password: {value}\n"));
        assert_eq!(YamlLoader::load_from_str(&output).unwrap()[0], node);
    }
}

#[test]
fn ambiguous_and_syntactically_special_strings_stay_quoted() {
    for value in [
        "",
        "yes",
        "NO",
        "on",
        "False",
        "null",
        "~",
        "123",
        "-12",
        "0123",
        "0xFF",
        "0b11",
        "1_000",
        "1:20",
        "1.25",
        ".inf",
        ".NaN",
        "2026-10-07",
        "2026-10-7T21:28:40",
        "2026-10-07 21:28:40",
        "2026-10-07 21:28:40.125 +03:00",
        "2026-10-07 21:28:40Z",
        "<<",
        "=",
        "1e3",
        "0o17",
        " leading",
        "trailing ",
        "#comment",
        "a #comment",
        "a: b",
        "a:",
        "---document",
        "...document",
        "'quoted'",
        "it's: tricky",
        "[list]",
        "{map}",
        "- item",
        "? key",
        "&anchor",
        "*alias",
        "!tag",
        "@value",
    ] {
        let node = mapping(value);
        let output = dump(&node).unwrap();
        assert_eq!(
            output,
            format!("password: '{}'\n", value.replace('\'', "''")),
            "{value:?}"
        );
        assert_eq!(YamlLoader::load_from_str(&output).unwrap()[0], node);
    }
}

#[test]
fn control_characters_and_multiline_strings_round_trip() {
    for value in [
        "first\nsecond\n",
        " spaced \n next",
        "a\tb",
        "a\rb",
        "\0\u{7}\u{8}",
        "\u{7f}\u{80}\u{85}\u{9f}",
        "\u{feff}",
        "a\u{2028}b\u{2029}c",
        "\u{ffff}\u{10ffff}",
    ] {
        let node = mapping(value);
        let output = dump(&node).unwrap();
        assert!(output.starts_with("password: \""), "{output:?}");
        assert_eq!(
            YamlLoader::load_from_str(&output).unwrap()[0],
            node,
            "{output:?}"
        );
    }
}

#[test]
fn nested_maps_sequences_and_scalar_types_round_trip() {
    let input = "group:\n  entry:\n    password: 'yes'\n    username: person\n    keywords:\n    - Gmail\n    - a,b\n    enabled: true\n    count: 42\n    nothing: null\n    empty_list: []\n    empty_map: {}\n";
    let node = YamlLoader::load_from_str(input).unwrap().remove(0);
    let output = dump(&node).unwrap();
    assert_eq!(output, input);
    assert_eq!(YamlLoader::load_from_str(&output).unwrap()[0], node);

    let nested = YamlLoader::load_from_str("items:\n- [one, two]\n- {key: value}\n")
        .unwrap()
        .remove(0);
    let output = dump(&nested).unwrap();
    assert_eq!(YamlLoader::load_from_str(&output).unwrap()[0], nested);
}

#[test]
fn string_keys_use_the_same_safe_quoting_rules() {
    let mut map = yaml_rust::yaml::Hash::new();
    for key in ["yes", "123", "2026-10-07", "a: b", "a#b", "a,b"] {
        map.insert(Yaml::String(key.into()), Yaml::String("value".into()));
    }
    let node = Yaml::Hash(map);
    let output = dump(&node).unwrap();
    assert_eq!(YamlLoader::load_from_str(&output).unwrap()[0], node);
    assert!(output.contains("'yes': value\n"));
    assert!(output.contains("a#b: value\n"));
}

#[test]
fn ascii_characters_round_trip_in_keys_and_values() {
    for byte in 0..=127 {
        let ch = char::from(byte);
        for value in [
            ch.to_string(),
            format!("{ch}secret"),
            format!("a{ch}b"),
            format!("secret{ch}"),
        ] {
            let mut map = yaml_rust::yaml::Hash::new();
            map.insert(Yaml::String(value.clone()), Yaml::String(value.clone()));
            let node = Yaml::Hash(map);
            let output = dump(&node).unwrap();
            assert_eq!(
                YamlLoader::load_from_str(&output).unwrap()[0],
                node,
                "{value:?}: {output:?}"
            );
        }
    }
}

#[test]
fn long_mapping_keys_use_explicit_key_notation() {
    for key in ["a".repeat(1025), "'".repeat(600)] {
        let mut map = yaml_rust::yaml::Hash::new();
        map.insert(Yaml::String(key), Yaml::String("value".into()));
        let node = Yaml::Hash(map);
        let output = dump(&node).unwrap();
        assert!(output.starts_with("? "));
        assert_eq!(YamlLoader::load_from_str(&output).unwrap()[0], node);
    }
}
