use std::fs;

use yaml_rust::Yaml;

use super::{as_number, charset, generate_password, resolve_wordlist};
use crate::config_value;

#[test]
/// Verify that generated passwords have the requested length and contain only selected characters.
fn generates_with_requested_character_set_and_length() {
    let password = generate_password(32, None, "digits", None, true)
        .unwrap()
        .unwrap();
    assert_eq!(password.len(), 32);
    assert!(password.chars().all(|character| character.is_ascii_digit()));
}

#[test]
/// Verify passphrase word counts and CRLF/blank-line handling in wordlists.
fn generates_passphrases_from_wordlist() {
    let path = std::env::temp_dir().join(format!("passata-wordlist-{}", std::process::id()));
    fs::write(&path, "alpha\r\n\r\nbeta\r\n").unwrap();
    let password = generate_password(8, None, "full", path.to_str(), true)
        .unwrap()
        .unwrap();
    let parts: Vec<_> = password.split(' ').collect();
    assert_eq!(parts.len(), 8);
    assert!(parts.iter().all(|word| *word == "alpha" || *word == "beta"));
    fs::remove_file(path).unwrap();
}

#[test]
/// Verify rejection of empty pools, zero lengths, and invalid or excessive entropy targets.
fn rejects_empty_wordlists_and_invalid_generation_sizes() {
    let path = std::env::temp_dir().join(format!("passata-empty-wordlist-{}", std::process::id()));
    fs::write(&path, "\n \r\n").unwrap();
    assert_eq!(
        generate_password(8, None, "full", path.to_str(), true),
        Err(String::from("The selected password pool is empty"))
    );
    fs::remove_file(path).unwrap();

    assert_eq!(
        generate_password(0, None, "digits", None, true),
        Err(String::from("Password length must be greater than zero"))
    );
    for entropy in [0.0, -1.0, f64::NAN, f64::INFINITY] {
        assert_eq!(
            generate_password(20, Some(entropy), "digits", None, true),
            Err(String::from("Entropy must be a finite positive number"))
        );
    }
    assert_eq!(
        generate_password(20, Some(f64::MAX), "digits", None, true),
        Err(String::from("Requested entropy is too large"))
    );
}

#[test]
/// Verify standalone generation succeeds even when the database path does not exist.
fn generating_without_a_name_does_not_read_the_database() {
    let matches = crate::cli()
        .try_get_matches_from([
            "passata",
            "generate",
            "--force",
            "--no-clip",
            "--length",
            "32",
        ])
        .unwrap();
    let (_, args) = matches.subcommand().unwrap();
    assert!(
        super::generate(
            "/path/that/does/not/exist",
            args,
            None,
            &Yaml::Hash(Default::default()),
            "",
            &mut crate::database::DatabaseHooks::new(std::path::Path::new(
                "/path/that/does/not/exist/config.yml",
            )),
        )
        .is_ok()
    );
}

#[test]
/// Verify case-insensitive character-set lookup and rejection of unknown names.
fn charset_names_are_case_insensitive_and_unknown_names_fail() {
    assert_eq!(charset("LETTERS").unwrap().len(), 52);
    assert_eq!(charset("digits").unwrap(), "0123456789");
    assert_eq!(charset("AlNum").unwrap().len(), 62);
    assert!(charset("symbols").unwrap_err().contains("Invalid charset"));
}

#[test]
/// Verify that entropy overrides the supplied length and rounds up to meet the target.
fn entropy_sets_a_minimum_generated_length() {
    let password = generate_password(1, Some(20.0), "digits", None, true)
        .unwrap()
        .unwrap();
    assert_eq!(password.len(), 7);
    assert!(password.chars().all(|character| character.is_ascii_digit()));
}

#[test]
/// Verify that an entropy target is rejected for a wordlist with no choice between items.
fn entropy_rejects_a_single_item_wordlist() {
    let path = std::env::temp_dir().join(format!("passata-single-wordlist-{}", std::process::id()));
    fs::write(&path, "only-word\n").unwrap();
    let result = generate_password(4, Some(32.0), "full", path.to_str(), true);
    fs::remove_file(path).unwrap();
    assert_eq!(
        result,
        Err(String::from(
            "Cannot calculate password length for a one-item pool"
        ))
    );
}

#[test]
/// Verify that wordlist lookup accepts an existing explicit file path.
fn wordlist_lookup_accepts_an_explicit_existing_path() {
    let path = std::env::temp_dir().join(format!("passata-lookup-{}", std::process::id()));
    fs::write(&path, "word\n").unwrap();
    assert_eq!(resolve_wordlist(path.to_str().unwrap()).unwrap(), path);
    fs::remove_file(path).unwrap();
}

#[test]
/// Verify numeric configuration parsing and lookup across supported YAML scalar types.
fn yaml_generation_settings_accept_numeric_representations() {
    assert_eq!(as_number::<u64>(&Yaml::String("12".into())), Some(12));
    assert_eq!(as_number::<u64>(&Yaml::Integer(34)), Some(34));
    assert_eq!(as_number::<f64>(&Yaml::Real("1.25".into())), Some(1.25));
    assert_eq!(as_number::<u64>(&Yaml::String("invalid".into())), None);
    let config = Yaml::Hash(
        vec![(Yaml::String("length".into()), Yaml::Integer(16))]
            .into_iter()
            .collect(),
    );
    assert_eq!(config_value(&config, "length"), Some(&Yaml::Integer(16)));
}

#[test]
/// Verify that missing wordlist names produce an informative lookup error.
fn wordlist_lookup_reports_missing_names() {
    let error = resolve_wordlist("passata-no-such-wordlist-for-test").unwrap_err();
    assert!(error.starts_with("Wordlist 'passata-no-such-wordlist-for-test' not found."));
}
