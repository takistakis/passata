use super::{dump, load};
use yaml_rust::Yaml;

#[test]
fn passwords_and_nested_fields_round_trip_with_native_yaml() {
    for password in [
        "secret",
        "yes",
        "123",
        "a: b",
        "'quoted'",
        "first\nsecond\n",
        "a\tb",
        "Ελληνικά",
        "🔑",
    ] {
        let mut entry = yaml_rust::yaml::Hash::new();
        entry.insert(
            Yaml::String("password".into()),
            Yaml::String(password.into()),
        );
        entry.insert(
            Yaml::String("keywords".into()),
            Yaml::Array(vec![Yaml::String("mail".into()), Yaml::Boolean(true)]),
        );
        let node = Yaml::Hash(entry);
        assert_eq!(load(&dump(&node).unwrap()).unwrap(), vec![node]);
    }
}

#[test]
fn empty_database_is_written_without_content() {
    assert_eq!(dump(&Yaml::Hash(Default::default())).unwrap(), "");
}
