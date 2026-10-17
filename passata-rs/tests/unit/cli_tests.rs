use crate::{cli, config_value, expand_home, load_config, yaml_u64};
use std::path::PathBuf;
use yaml_rust::Yaml;

#[test]
/// Verify that empty configuration files and valid mappings load successfully.
fn loads_empty_and_valid_configuration_files() {
    let path = std::env::temp_dir().join(format!("passata-config-{}", std::process::id()));
    std::fs::write(&path, "").unwrap();
    let empty = load_config(&path).unwrap();
    assert!(empty.as_hash().unwrap().is_empty());

    std::fs::write(&path, "database: ~/vault\n").unwrap();
    let config = load_config(&path).unwrap();
    assert_eq!(
        config_value(&config, "database").unwrap().as_str(),
        Some("~/vault")
    );
    std::fs::remove_file(path).unwrap();
}

#[test]
/// Verify that malformed YAML, non-mapping roots, and multiple documents are rejected.
fn rejects_invalid_config_documents() {
    let path = std::env::temp_dir().join(format!("passata-invalid-config-{}", std::process::id()));
    for (contents, expected) in [
        ("[invalid", "Invalid configuration YAML:"),
        ("- item\n", "Invalid configuration"),
        (
            "---\na: 1\n---\nb: 2\n",
            "Invalid configuration YAML: multiple documents",
        ),
    ] {
        std::fs::write(&path, contents).unwrap();
        assert!(
            load_config(&path).unwrap_err().starts_with(expected),
            "unexpected error for {:?}",
            contents
        );
    }
    std::fs::remove_file(path).unwrap();
}

#[test]
/// Verify that integer settings accept nonnegative integers and strings, but not negatives or reals.
fn parses_nonnegative_integer_settings() {
    assert_eq!(yaml_u64(&Yaml::Integer(5)), Some(5));
    assert_eq!(yaml_u64(&Yaml::String("42".into())), Some(42));
    assert_eq!(yaml_u64(&Yaml::Integer(-1)), None);
    assert_eq!(yaml_u64(&Yaml::Real("1.5".into())), None);
}

#[test]
/// Verify home expansion without altering relative paths or another user's home notation.
fn expands_home_prefix_without_changing_relative_paths() {
    let home = std::env::var_os("HOME").map(PathBuf::from);
    if let Some(home) = home {
        assert_eq!(expand_home("~"), home);
        assert_eq!(expand_home("~/vault"), home.join("vault"));
    }
    assert_eq!(
        expand_home("relative/config.yml"),
        PathBuf::from("relative/config.yml")
    );
    assert_eq!(expand_home("~other/config"), PathBuf::from("~other/config"));
}

#[test]
/// Verify that a subcommand is required and generation options receive typed values.
fn cli_requires_subcommand_and_parses_generate_options() {
    assert!(cli().try_get_matches_from(["passata"]).is_err());
    let matches = cli()
        .try_get_matches_from([
            "passata",
            "generate",
            "--length",
            "12",
            "--charset",
            "digits",
        ])
        .unwrap();
    let (_, args) = matches.subcommand().unwrap();
    assert_eq!(args.get_one::<u32>("length"), Some(&12));
    assert_eq!(args.get_one::<String>("charset").unwrap(), "digits");
}

#[test]
fn cli_parses_mv_sources_destination_and_force() {
    for input in [
        vec!["passata", "mv", "old", "new"],
        vec!["passata", "mv", "-f", "one", "two", "group/"],
        vec!["passata", "mv", "one", "two", "/", "--force"],
    ] {
        let matches = cli().try_get_matches_from(input.clone()).unwrap();
        let args = matches.subcommand_matches("mv").unwrap();
        let sources = args
            .get_many::<String>("source")
            .unwrap()
            .collect::<Vec<_>>();
        assert_eq!(sources.len(), if input.len() == 4 { 1 } else { 2 });
        assert_eq!(args.get_flag("force"), input.len() != 4);
        assert!(args.get_one::<String>("dest").is_some());
    }
    for input in [vec!["passata", "mv"], vec!["passata", "mv", "only-source"]] {
        assert!(cli().try_get_matches_from(input).is_err());
    }
}

#[test]
fn cli_parses_rm_names_force_and_recursive() {
    let matches = cli()
        .try_get_matches_from(["passata", "rm", "-fr", "internet/social", "old"])
        .unwrap();
    let args = matches.subcommand_matches("rm").unwrap();
    assert_eq!(
        args.get_many::<String>("names")
            .unwrap()
            .map(String::as_str)
            .collect::<Vec<_>>(),
        vec!["internet/social", "old"]
    );
    assert!(args.get_flag("force"));
    assert!(args.get_flag("recursive"));
    assert!(cli().try_get_matches_from(["passata", "rm"]).is_err());
}

#[test]
fn cli_parses_insert_password_and_force() {
    let matches = cli()
        .try_get_matches_from([
            "passata",
            "insert",
            "account",
            "--password",
            "secret",
            "--force",
        ])
        .unwrap();
    let args = matches.subcommand_matches("insert").unwrap();
    assert_eq!(
        args.get_one::<String>("name").map(String::as_str),
        Some("account")
    );
    assert_eq!(
        args.get_one::<String>("password").map(String::as_str),
        Some("secret")
    );
    assert!(args.get_flag("force"));
    assert!(cli().try_get_matches_from(["passata", "insert"]).is_err());
}
