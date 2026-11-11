use std::os::unix::fs::PermissionsExt;
use std::process::Command;

#[test]
fn init_creates_configuration_and_encrypted_empty_database() {
    let directory = std::env::temp_dir().join(format!(
        "passata-init-cli-{}-{}",
        std::process::id(),
        std::time::SystemTime::now()
            .duration_since(std::time::UNIX_EPOCH)
            .unwrap()
            .as_nanos()
    ));
    let bin = directory.join("bin");
    std::fs::create_dir_all(&bin).unwrap();
    let gpg = bin.join("gpg");
    std::fs::write(
        &gpg,
        "#!/bin/sh\n[ \"$1\" = \"--encrypt\" ] || exit 2\n/bin/cat >/dev/null\nprintf 'fake ciphertext'\n",
    )
    .unwrap();
    std::fs::set_permissions(&gpg, std::fs::Permissions::from_mode(0o700)).unwrap();

    let config = directory.join("config/config.yml");
    let state_home = directory.join("state");
    let database = directory.join("vault.gpg");
    let output = Command::new(env!("CARGO_BIN_EXE_passata-rs"))
        .arg("--config")
        .arg(&config)
        .args(["init", "--force", "--gpg-id", "user@example.com", "--path"])
        .arg(&database)
        .env("PATH", &bin)
        .env("XDG_STATE_HOME", &state_home)
        .output()
        .unwrap();

    assert!(
        output.status.success(),
        "stdout: {}\nstderr: {}",
        String::from_utf8_lossy(&output.stdout),
        String::from_utf8_lossy(&output.stderr)
    );
    let contents = std::fs::read_to_string(&config).unwrap();
    assert!(contents.contains(&format!("database: {}", database.display())));
    assert!(contents.contains("gpg_id: user@example.com"));
    assert_eq!(
        std::fs::read_to_string(&database).unwrap(),
        "fake ciphertext"
    );
    assert!(!directory.join("vault.lock").exists());
    let lock_directory = state_home.join("passata/locks");
    let lock_files: Vec<_> = std::fs::read_dir(&lock_directory)
        .unwrap()
        .map(|entry| entry.unwrap().path())
        .collect();
    assert_eq!(lock_files.len(), 1);
    assert!(lock_files[0].is_file());
    std::fs::remove_dir_all(directory).unwrap();
}
