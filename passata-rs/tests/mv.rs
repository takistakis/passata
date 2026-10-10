// Copyright 2026 Panagiotis Ktistakis <panktist@gmail.com>
//
// This file is part of passata-rs.
//
// passata-rs is free software: you can redistribute it and/or modify
// it under the terms of the GNU General Public License as published by
// the Free Software Foundation, either version 3 of the License, or
// (at your option) any later version.
//
// passata-rs is distributed in the hope that it will be useful,
// but WITHOUT ANY WARRANTY; without even the implied warranty of
// MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
// GNU General Public License for more details.
//
// You should have received a copy of the GNU General Public License
// along with passata-rs.  If not, see <http://www.gnu.org/licenses/>.

use std::fs;
use std::io::Write;
use std::os::unix::fs::PermissionsExt;
use std::path::PathBuf;
use std::process::{Command, Output, Stdio};
use std::sync::atomic::{AtomicUsize, Ordering};

use yaml_rust::{Yaml, YamlLoader};

struct Fixture {
    directory: PathBuf,
}

impl Fixture {
    fn new() -> Self {
        static NEXT_FIXTURE: AtomicUsize = AtomicUsize::new(0);
        let nonce = std::time::SystemTime::now()
            .duration_since(std::time::UNIX_EPOCH)
            .unwrap()
            .as_nanos();
        let directory = PathBuf::from("/tmp").join(format!(
            "passata-mv-{}-{}-{}",
            std::process::id(),
            nonce,
            NEXT_FIXTURE.fetch_add(1, Ordering::Relaxed),
        ));
        fs::create_dir(&directory).unwrap();
        let fixture = Self { directory };
        let home = fixture.directory.join("gnupg");
        fs::create_dir(&home).unwrap();
        fs::set_permissions(home, fs::Permissions::from_mode(0o700)).unwrap();
        let output = fixture
            .gpg()
            .args([
                "--pinentry-mode",
                "loopback",
                "--passphrase",
                "",
                "--quick-generate-key",
                "Passata Move Test <passata-mv@example.invalid>",
                "rsa2048",
                "encr",
                "0",
            ])
            .output()
            .unwrap();
        assert!(output.status.success(), "{:?}", output);
        let plain = fixture.directory.join("database.yml");
        fs::write(
            &plain,
            "internet:\n  github:\n    password: gh\n  social:\n    reddit:\n      password: rdt\n      username: sakis\n    twitter:\n      password: twt\n",
        )
        .unwrap();
        let output = fixture
            .gpg()
            .args([
                "--trust-model",
                "always",
                "--encrypt",
                "--recipient",
                "passata-mv@example.invalid",
                "--output",
            ])
            .arg(fixture.directory.join("database.gpg"))
            .arg(plain)
            .output()
            .unwrap();
        assert!(output.status.success(), "{:?}", output);
        fixture.configure("");
        fixture
    }

    fn gpg(&self) -> Command {
        let mut command = Command::new("gpg");
        command
            .env("GNUPGHOME", self.directory.join("gnupg"))
            .args(["--batch", "--yes"]);
        command
    }

    fn configure(&self, settings: &str) {
        fs::write(
            self.directory.join("config.yml"),
            format!(
                "database: {}\ngpg_id: passata-mv@example.invalid\n{}",
                self.directory.join("database.gpg").display(),
                settings,
            ),
        )
        .unwrap();
    }

    fn run(&self, args: &[&str], input: &str) -> Output {
        let mut command = vec!["mv"];
        command.extend_from_slice(args);
        self.run_command(&command, input)
    }

    fn run_command(&self, args: &[&str], input: &str) -> Output {
        let mut child = Command::new(env!("CARGO_BIN_EXE_passata-rs"))
            .env("GNUPGHOME", self.directory.join("gnupg"))
            .env("PASSATA_HOOK_TEST_DIR", &self.directory)
            .env("PAGER", "cat")
            .arg("--config")
            .arg(self.directory.join("config.yml"))
            .args(args)
            .stdin(Stdio::piped())
            .stdout(Stdio::piped())
            .stderr(Stdio::piped())
            .spawn()
            .unwrap();
        child
            .stdin
            .take()
            .unwrap()
            .write_all(input.as_bytes())
            .unwrap();
        child.wait_with_output().unwrap()
    }

    fn hook(&self, name: &str, body: &str) {
        let directory = self.directory.join("hooks");
        fs::create_dir_all(&directory).unwrap();
        let path = directory.join(name);
        fs::write(
            &path,
            format!("#!/bin/sh\ntest \"$#\" -eq 0 || exit 42\n{}\n", body),
        )
        .unwrap();
        fs::set_permissions(path, fs::Permissions::from_mode(0o700)).unwrap();
    }

    fn read(&self) -> Yaml {
        let output = self
            .gpg()
            .arg("--decrypt")
            .arg(self.directory.join("database.gpg"))
            .output()
            .unwrap();
        assert!(output.status.success(), "{:?}", output);
        YamlLoader::load_from_str(&String::from_utf8(output.stdout).unwrap())
            .unwrap()
            .remove(0)
    }
}

impl Drop for Fixture {
    fn drop(&mut self) {
        let _ = Command::new("gpgconf")
            .env("GNUPGHOME", self.directory.join("gnupg"))
            .args(["--kill", "gpg-agent"])
            .output();
        if let Err(error) = fs::remove_dir_all(&self.directory) {
            eprintln!(
                "Couldn't clean up test fixture {}: {}",
                self.directory.display(),
                error
            );
        }
    }
}

#[test]
fn mv_persists_moves_and_never_writes_on_decline_or_error() {
    use std::os::unix::io::AsRawFd;

    let fixture = Fixture::new();
    let database = fixture.directory.join("database.gpg");
    let original = fs::read(&database).unwrap();
    let lock = fs::OpenOptions::new()
        .create(true)
        .append(true)
        .open(database.with_extension("lock"))
        .unwrap();
    assert_eq!(
        unsafe { libc::flock(lock.as_raw_fd(), libc::LOCK_EX | libc::LOCK_NB) },
        0
    );
    let output = fixture.run(&["internet", "renamed"], "");
    assert!(!output.status.success());
    assert_eq!(
        String::from_utf8(output.stderr).unwrap(),
        "Another passata process is editing the database\n"
    );
    assert_eq!(fs::read(&database).unwrap(), original);
    drop(lock);

    let output = fixture.run(&["internet/social/reddit", "internet/github"], "n\n");
    assert!(output.status.success(), "{:?}", output);
    assert_eq!(
        String::from_utf8(output.stdout).unwrap(),
        "Overwrite internet/github? [y/N]: "
    );
    assert_eq!(fs::read(&database).unwrap(), original);

    for (args, error) in [
        (
            vec!["internet/github", "missing", "new/"],
            "missing not found\n",
        ),
        (
            vec!["internet", "internet/social/deep"],
            "Cannot move 'internet' into its own subdirectory\n",
        ),
        (
            vec!["internet/github", "internet/social/reddit", "new"],
            "new is not a group\n",
        ),
    ] {
        let output = fixture.run(&args, "");
        assert!(!output.status.success(), "{:?}", output);
        assert_eq!(String::from_utf8(output.stderr).unwrap(), error);
        assert_eq!(fs::read(&database).unwrap(), original);
    }

    let output = fixture.run(&["internet/social/reddit", "internet/github"], "yes\n");
    assert!(output.status.success(), "{:?}", output);
    assert_eq!(
        fixture.read()["internet"]["github"]["username"].as_str(),
        Some("sakis")
    );
    assert_eq!(
        fixture.read()["internet"]["social"]["reddit"],
        Yaml::BadValue
    );

    let output = fixture.run(&["internet/github", "internet/social/twitter", "new/"], "");
    assert!(output.status.success(), "{:?}", output);
    let db = fixture.read();
    assert_eq!(db["internet"], Yaml::BadValue);
    assert_eq!(db["new"]["github"]["password"].as_str(), Some("rdt"));
    assert_eq!(db["new"]["twitter"]["password"].as_str(), Some("twt"));
    let output = fixture.run(&["new/", "renamed/"], "");
    assert!(output.status.success(), "{:?}", output);
    let output = fixture.run(&["renamed/github", "renamed/twitter", "/"], "");
    assert!(output.status.success(), "{:?}", output);
    assert_eq!(fixture.read()["renamed"], Yaml::BadValue);

    fixture.configure("force: true\nmv:\n  force: false\n");
    let original = fs::read(&database).unwrap();
    let output = fixture.run(&["github", "twitter"], "");
    assert!(output.status.success(), "{:?}", output);
    assert_eq!(fs::read(&database).unwrap(), original);
    let output = fixture.run(&["github", "twitter", "--force"], "");
    assert!(output.status.success(), "{:?}", output);
    assert!(output.stdout.is_empty());
    assert_eq!(fixture.read()["twitter"]["password"].as_str(), Some("rdt"));

    fixture.configure("mv:\n  force: true\n");
    let output = fixture.run(&["twitter", "other"], "");
    assert!(output.status.success(), "{:?}", output);
    let output = fixture.run(&["other", "other"], "");
    assert!(output.status.success(), "{:?}", output);
    assert!(output.stdout.is_empty());
    assert_eq!(fixture.read()["other"]["password"].as_str(), Some("rdt"));

    fixture.configure("force: true\n");
    let output = fixture.run(&["other", "other"], "");
    assert!(output.status.success(), "{:?}", output);
    assert!(output.stdout.is_empty());

    fs::write(
        fixture.directory.join("config.yml"),
        format!(
            "database: {}\ngpg_id: nonexistent-recipient@example.invalid\n",
            database.display()
        ),
    )
    .unwrap();
    let original = fs::read(&database).unwrap();
    let output = fixture.run(&["other", "unsaved"], "");
    assert!(!output.status.success());
    assert!(
        String::from_utf8(output.stderr)
            .unwrap()
            .starts_with("gpg encryption failed:")
    );
    assert_eq!(fs::read(&database).unwrap(), original);
}

#[test]
fn hooks_run_for_reads_and_only_successful_changed_writes() {
    let fixture = Fixture::new();
    fixture.hook("pre-read", "printf 'pre\\n'\nprintf 'hidden-pre\\n' >&2");
    fixture.hook(
        "post-write",
        "printf 'post\\n'\nprintf 'hidden-post\\n' >&2\n\
             gpg --batch --decrypt \"$PASSATA_HOOK_TEST_DIR/database.gpg\" \
             > \"$PASSATA_HOOK_TEST_DIR/post-write.yml\"",
    );
    for args in [
        vec!["ls"],
        vec!["tree"],
        vec!["show", "--no-clip"],
        vec!["find", "github", "--no-clip"],
    ] {
        let output = fixture.run_command(&args, "");
        assert!(output.status.success(), "{:?}", output);
        let stdout = String::from_utf8(output.stdout).unwrap();
        assert!(stdout.starts_with("pre\n"), "{stdout}");
        assert!(!stdout.contains("post\n"), "{stdout}");
        assert!(output.stderr.is_empty(), "{:?}", output.stderr);
    }
    let original = fs::read(fixture.directory.join("database.gpg")).unwrap();
    for (args, input, succeeds) in [
        (
            vec!["internet/github", "internet/social/twitter"],
            "n\n",
            true,
        ),
        (vec!["missing", "new"], "", false),
    ] {
        let output = fixture.run(&args, input);
        assert_eq!(output.status.success(), succeeds, "{:?}", output);
        let stdout = String::from_utf8(output.stdout).unwrap();
        assert!(stdout.starts_with("pre\n"), "{stdout}");
        assert!(!stdout.contains("post\n"), "{stdout}");
        assert_eq!(
            fs::read(fixture.directory.join("database.gpg")).unwrap(),
            original
        );
    }
    fixture.configure("gpg_id: nonexistent-recipient@example.invalid\n");
    let output = fixture.run(&["internet/github", "new"], "");
    assert!(!output.status.success(), "{:?}", output);
    assert_eq!(output.stdout, b"pre\n");
    assert_eq!(
        fs::read(fixture.directory.join("database.gpg")).unwrap(),
        original
    );
    fixture.configure("");

    let output = fixture.run(&["internet/github", "new"], "");
    assert!(output.status.success(), "{:?}", output);
    assert_eq!(output.stdout, b"pre\npost\n");
    assert!(output.stderr.is_empty(), "{:?}", output.stderr);
    let synced = YamlLoader::load_from_str(
        &fs::read_to_string(fixture.directory.join("post-write.yml")).unwrap(),
    )
    .unwrap()
    .remove(0);
    assert_eq!(synced["new"]["password"].as_str(), Some("gh"));
    assert_eq!(synced, fixture.read());

    let written = fs::read(fixture.directory.join("database.gpg")).unwrap();
    let output = fixture.run(&["new", "new", "--force"], "");
    assert!(output.status.success(), "{:?}", output);
    assert_eq!(output.stdout, b"pre\n");
    assert_eq!(
        fs::read(fixture.directory.join("database.gpg")).unwrap(),
        written
    );
}

#[test]
fn pre_read_can_restore_the_database_and_runs_before_locking() {
    use std::os::unix::io::AsRawFd;

    let fixture = Fixture::new();
    let database = fixture.directory.join("database.gpg");
    fs::rename(&database, fixture.directory.join("backup.gpg")).unwrap();
    fixture.hook(
        "pre-read",
        "printf 'pre\\n'\ncp \"$PASSATA_HOOK_TEST_DIR/backup.gpg\" \
             \"$PASSATA_HOOK_TEST_DIR/database.gpg\"",
    );
    let output = fixture.run_command(&["ls"], "");
    assert!(output.status.success(), "{:?}", output);
    assert!(output.stdout.starts_with(b"pre\n"));
    assert!(database.is_file());

    let lock = fs::OpenOptions::new()
        .create(true)
        .append(true)
        .open(database.with_extension("lock"))
        .unwrap();
    assert_eq!(
        unsafe { libc::flock(lock.as_raw_fd(), libc::LOCK_EX | libc::LOCK_NB) },
        0
    );
    let output = fixture.run(&["internet/github", "new"], "");
    assert!(!output.status.success(), "{:?}", output);
    assert_eq!(output.stdout, b"pre\n");
    assert_eq!(
        output.stderr,
        b"Another passata process is editing the database\n"
    );
    drop(lock);
}

#[test]
fn hook_failures_follow_pre_read_and_exit_callback_semantics() {
    let fixture = Fixture::new();
    fixture.hook(
        "pre-read",
        "printf 'pre\\n'\nprintf 'hidden\\n' >&2\nexit 7",
    );
    fixture.hook("post-write", "printf 'post\\n'");
    let database = fixture.directory.join("database.gpg");
    let original = fs::read(&database).unwrap();
    let output = fixture.run(&["internet/github", "new"], "");
    assert!(!output.status.success(), "{:?}", output);
    assert_eq!(output.stdout, b"pre\n");
    let stderr = String::from_utf8(output.stderr).unwrap();
    assert!(stderr.contains("pre-read"), "{stderr}");
    assert!(stderr.contains("7"), "{stderr}");
    assert!(!stderr.contains("hidden"), "{stderr}");
    assert_eq!(fs::read(&database).unwrap(), original);

    fs::set_permissions(
        fixture.directory.join("hooks/pre-read"),
        fs::Permissions::from_mode(0o600),
    )
    .unwrap();
    let output = fixture.run_command(&["ls"], "");
    assert!(!output.status.success(), "{:?}", output);
    assert!(
        String::from_utf8(output.stderr)
            .unwrap()
            .contains("Couldn't execute hook")
    );

    fs::remove_file(fixture.directory.join("hooks/pre-read")).unwrap();
    fs::create_dir(fixture.directory.join("hooks/pre-read")).unwrap();
    fixture.hook(
        "post-write",
        "printf 'post\\n'\nprintf 'hidden\\n' >&2\nexit 9",
    );
    let output = fixture.run(&["internet/github", "new"], "");
    assert!(output.status.success(), "{:?}", output);
    assert_eq!(output.stdout, b"post\n");
    let stderr = String::from_utf8(output.stderr).unwrap();
    assert!(stderr.contains("post-write"), "{stderr}");
    assert!(stderr.contains("9"), "{stderr}");
    assert!(!stderr.contains("hidden"), "{stderr}");
    assert_eq!(fixture.read()["new"]["password"].as_str(), Some("gh"));
}

#[test]
fn generate_hooks_finish_after_output_even_when_later_work_fails() {
    let fixture = Fixture::new();
    fixture.hook("pre-read", "printf 'pre\\n'");
    fixture.hook("post-write", "printf 'post\\n'");
    let output = fixture.run_command(&["generate", "--force", "--no-clip"], "");
    assert!(output.status.success(), "{:?}", output);
    let stdout = String::from_utf8(output.stdout).unwrap();
    assert!(
        !stdout.contains("pre\n") && !stdout.contains("post\n"),
        "{stdout}"
    );

    let output = fixture.run_command(&["generate", "new", "--force", "--no-clip", "--print"], "");
    assert!(output.status.success(), "{:?}", output);
    let stdout = String::from_utf8(output.stdout).unwrap();
    let password = fixture.read()["new"]["password"]
        .as_str()
        .unwrap()
        .to_owned();
    assert!(stdout.contains("pre\n"), "{stdout}");
    assert!(stdout.ends_with(&format!("{password}\npost\n")), "{stdout}");

    let bin = fixture.directory.join("bin");
    fs::create_dir(&bin).unwrap();
    for name in ["pbcopy", "xsel"] {
        let path = bin.join(name);
        fs::write(&path, "#!/bin/sh\ncat >/dev/null\nexit 3\n").unwrap();
        fs::set_permissions(path, fs::Permissions::from_mode(0o700)).unwrap();
    }
    let mut paths = vec![bin];
    paths.extend(std::env::split_paths(&std::env::var_os("PATH").unwrap()));
    let output = Command::new(env!("CARGO_BIN_EXE_passata-rs"))
        .env("GNUPGHOME", fixture.directory.join("gnupg"))
        .env("PATH", std::env::join_paths(paths).unwrap())
        .arg("--config")
        .arg(fixture.directory.join("config.yml"))
        .args(["generate", "saved", "--force", "--clip"])
        .stdin(Stdio::null())
        .output()
        .unwrap();
    assert!(!output.status.success(), "{:?}", output);
    assert!(output.stdout.ends_with(b"pre\npost\n"), "{:?}", output);
    assert!(
        String::from_utf8(output.stderr)
            .unwrap()
            .contains("Clipboard command exited")
    );
    assert!(fixture.read()["saved"]["password"].as_str().is_some());
}
