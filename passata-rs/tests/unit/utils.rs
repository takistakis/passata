use super::{path_parts, scalar_string};
use yaml_rust::Yaml;

#[test]
/// Verify nested path splitting, trailing-slash handling, and rejection of empty components.
fn parses_nested_paths_and_group_suffixes() {
    assert_eq!(
        path_parts(Some("internet/social/")).unwrap(),
        vec!["internet", "social"]
    );
    assert_eq!(path_parts(Some("/")), Ok(Vec::<&str>::new()));
    assert_eq!(
        path_parts(Some("internet//social")),
        Err(String::from("Invalid path: internet//social"))
    );
}

#[test]
/// Verify that absent and root names yield no components and repeated trailing slashes are stripped.
fn parses_absent_and_root_paths() {
    assert_eq!(path_parts(None), Ok(Vec::<&str>::new()));
    assert_eq!(path_parts(Some("")), Ok(Vec::<&str>::new()));
    assert_eq!(path_parts(Some("group///")), Ok(vec!["group"]));
}

#[test]
/// Verify that leading slashes and empty internal components are rejected.
fn rejects_paths_with_empty_components() {
    assert_eq!(
        path_parts(Some("/internet")),
        Err(String::from("Invalid path: /internet"))
    );
    assert_eq!(
        path_parts(Some("internet//social/")),
        Err(String::from("Invalid path: internet//social/"))
    );
}

#[test]
/// Verify scalar text conversion, null formatting, and empty output for unsupported collections.
fn converts_yaml_scalars_to_strings() {
    assert_eq!(scalar_string(&Yaml::String("value".into())), "value");
    assert_eq!(scalar_string(&Yaml::Real("1.5".into())), "1.5");
    assert_eq!(scalar_string(&Yaml::Integer(42)), "42");
    assert_eq!(scalar_string(&Yaml::Boolean(false)), "false");
    assert_eq!(scalar_string(&Yaml::Null), "None");
    assert_eq!(scalar_string(&Yaml::Array(vec![])), "");
    assert_eq!(scalar_string(&Yaml::Hash(Default::default())), "");
}
