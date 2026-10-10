use std::os::unix::fs::PermissionsExt;
use std::path::Path;

use yaml_rust::{Yaml, YamlLoader};

use super::edit;
use crate::cli;

#[test]
fn editor_command_receives_config_path_and_arguments() {
    let directory =
        std::env::temp_dir().join(format!("passata-config-editor-{}", std::process::id()));
    std::fs::create_dir_all(&directory).unwrap();
    let editor = directory.join("fake editor");
    let config = directory.join("config.yml");
    let output = directory.join("args");
    std::fs::write(
        &editor,
        format!(
            "#!/bin/sh\nprintf '%s\\n' \"$@\" > '{}'\n",
            output.display()
        ),
    )
    .unwrap();
    std::fs::set_permissions(&editor, std::fs::Permissions::from_mode(0o700)).unwrap();
    std::fs::write(&config, "database: vault.gpg\n").unwrap();
    let command = format!("'{}' --wait", editor.display());
    let matches = cli()
        .try_get_matches_from(["passata", "config", "--editor", &command])
        .unwrap();
    let args = matches.subcommand_matches("config").unwrap();
    let command_config = Yaml::Hash(Default::default());
    let root_config = Yaml::Hash(Default::default());
    edit(
        Path::new(&config),
        args,
        Some(&command_config),
        &root_config,
    )
    .unwrap();
    assert_eq!(
        std::fs::read_to_string(output).unwrap(),
        format!("--wait\n{}\n", config.display())
    );
    std::fs::remove_dir_all(directory).unwrap();
}

#[test]
fn editor_uses_command_config_before_root_setting() {
    let mut docs = YamlLoader::load_from_str("editor: /command-editor\n").unwrap();
    let command_config = docs.remove(0);
    let mut docs = YamlLoader::load_from_str("editor: /root-editor\n").unwrap();
    let root_config = docs.remove(0);
    assert_eq!(
        super::editor_setting(Some(&command_config), &root_config),
        Some("/command-editor")
    );
}
