use std::path::Path;

use crate::cli;

#[test]
fn cli_parses_init_options() {
    let matches = cli()
        .try_get_matches_from([
            "passata",
            "--config",
            "/tmp/config.yml",
            "init",
            "--force",
            "--gpg-id",
            "user@example.com",
            "--path",
            "~/vault.gpg",
        ])
        .unwrap();
    let args = matches.subcommand_matches("init").unwrap();
    assert!(args.get_flag("force"));
    assert_eq!(
        args.get_one::<String>("gpg_id").map(String::as_str),
        Some("user@example.com")
    );
    assert_eq!(
        args.get_one::<String>("path").map(String::as_str),
        Some("~/vault.gpg")
    );
}

#[test]
fn writes_configuration_with_absolute_database_path() {
    let directory = std::env::temp_dir().join(format!(
        "passata-init-unit-{}-{}",
        std::process::id(),
        std::time::SystemTime::now()
            .duration_since(std::time::UNIX_EPOCH)
            .unwrap()
            .as_nanos()
    ));
    std::fs::create_dir_all(&directory).unwrap();
    let config = directory.join("nested/config.yml");
    let database = directory.join("vault.gpg");
    assert!(super::write_config(&config, &database, "user@example.com", true).unwrap());
    let loaded = crate::load_config(&config.to_path_buf()).unwrap();
    assert_eq!(
        crate::config_value(&loaded, "database").and_then(yaml_rust::Yaml::as_str),
        Some(database.to_str().unwrap())
    );
    assert_eq!(
        crate::config_value(&loaded, "gpg_id").and_then(yaml_rust::Yaml::as_str),
        Some("user@example.com")
    );
    std::fs::remove_dir_all(directory).unwrap();
}

#[test]
fn absolute_path_keeps_existing_absolute_paths() {
    let path = Path::new("/tmp/passata-init.gpg").to_path_buf();
    assert_eq!(super::absolute(path.clone()).unwrap(), path);
}

#[test]
fn absolute_path_resolves_relative_paths_against_current_directory() {
    let current = std::env::current_dir().unwrap();
    assert_eq!(
        super::absolute("vault.gpg".into()).unwrap(),
        current.join("vault.gpg")
    );
}
