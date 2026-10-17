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
use std::os::unix::fs::PermissionsExt;
use std::path::PathBuf;
use std::process::{Command, Output, Stdio};

struct Fixture {
    directory: PathBuf,
}

impl Fixture {
    /// Create an isolated GPG home, encrypted database, configuration, and clipboard stubs.
    fn new() -> Self {
        let nonce = std::time::SystemTime::now()
            .duration_since(std::time::UNIX_EPOCH)
            .unwrap()
            .as_nanos();
        let fixture = Self {
            // GPG's Unix sockets need a short path, including on macOS.
            directory: PathBuf::from("/tmp").join(format!(
                "passata-find-{}-{}",
                std::process::id(),
                nonce
            )),
        };
        fs::create_dir(&fixture.directory).unwrap();
        let home = fixture.directory.join("gnupg");
        fs::create_dir(&home).unwrap();
        fs::set_permissions(&home, fs::Permissions::from_mode(0o700)).unwrap();
        let output = fixture
            .gpg()
            .args([
                "--pinentry-mode",
                "loopback",
                "--passphrase",
                "",
                "--quick-generate-key",
                "Passata Test <passata-test@example.invalid>",
                "rsa2048",
                "encr",
                "0",
            ])
            .output()
            .unwrap();
        assert!(
            output.status.success(),
            "GPG key generation failed: {}",
            String::from_utf8_lossy(&output.stderr)
        );
        let plain = fixture.directory.join("database.yml");
        fs::write(
            &plain,
            "internet:\n  github:\n    password: gh\n  reddit:\n    password: rdt\n    username: sakis\n  social:\n    twitter:\n      password: twt\nserver:\n  password: srv\ngroup:\n  google:\n    username: user\n    password: pass\n    keywords:\n    - YouTube\n    - Gmail\n  missing:\n    username: user\n  null_entry:\n    password: null\n",
        )
        .unwrap();
        let database = fixture.directory.join("database.gpg");
        let output = fixture
            .gpg()
            .args(["--trust-model", "always", "--encrypt", "--recipient"])
            .arg("passata-test@example.invalid")
            .arg("--output")
            .arg(&database)
            .arg(plain)
            .output()
            .unwrap();
        assert!(
            output.status.success(),
            "GPG encryption failed: {}",
            String::from_utf8_lossy(&output.stderr)
        );
        fixture.configure("");

        let bin = fixture.directory.join("bin");
        fs::create_dir(&bin).unwrap();
        for name in ["pbcopy", "xsel"] {
            let script = bin.join(name);
            fs::write(&script, "#!/bin/sh\ncat > \"$PASSATA_TEST_CLIPBOARD\"\n").unwrap();
            fs::set_permissions(script, fs::Permissions::from_mode(0o700)).unwrap();
        }
        fixture
    }

    /// Build a noninteractive GPG command scoped to this fixture's keyring.
    fn gpg(&self) -> Command {
        let mut command = Command::new("gpg");
        command
            .env("GNUPGHOME", self.directory.join("gnupg"))
            .args(["--batch", "--yes"])
            .stdin(Stdio::null());
        command
    }

    /// Write the fixture database path and supplied settings to its configuration.
    fn configure(&self, settings: &str) {
        fs::write(
            self.directory.join("config.yml"),
            format!(
                "database: {}\n{}",
                self.directory.join("database.gpg").display(),
                settings
            ),
        )
        .unwrap();
    }

    /// Run the compiled `find` command with isolated configuration and clipboard handling.
    fn run(&self, args: &[&str]) -> Output {
        let mut paths = vec![self.directory.join("bin")];
        paths.extend(std::env::split_paths(
            &std::env::var_os("PATH").unwrap_or_default(),
        ));
        Command::new(env!("CARGO_BIN_EXE_passata-rs"))
            .env("GNUPGHOME", self.directory.join("gnupg"))
            .env("PATH", std::env::join_paths(paths).unwrap())
            .env("PAGER", "cat")
            .env("PASSATA_TEST_CLIPBOARD", self.directory.join("clipboard"))
            .args(["--config"])
            .arg(self.directory.join("config.yml"))
            .args(["find"])
            .args(args)
            .stdin(Stdio::null())
            .output()
            .unwrap()
    }

    /// Require a successful CLI invocation and decode its standard output as UTF-8.
    fn output(&self, args: &[&str]) -> String {
        let output = self.run(args);
        assert!(
            output.status.success(),
            "find {:?} failed: {}",
            args,
            String::from_utf8_lossy(&output.stderr)
        );
        String::from_utf8(output.stdout).unwrap()
    }
}

impl Drop for Fixture {
    /// Stop the fixture's GPG agent and remove its temporary files.
    fn drop(&mut self) {
        // Stop only the agent belonging to this isolated test home.
        let _ = Command::new("gpgconf")
            .env("GNUPGHOME", self.directory.join("gnupg"))
            .args(["--kill", "gpg-agent"])
            .output();
        fs::remove_dir_all(&self.directory).unwrap();
    }
}

#[test]
/// Verify CLI output, clipboard behavior, and configuration/flag precedence against Python behavior.
fn find_matches_python_outputs_and_configuration_precedence() {
    let fixture = Fixture::new();
    assert_eq!(
        fixture.output(&["RED"]),
        ".\n└── internet\n    └── reddit\n"
    );
    assert_eq!(
        fixture.output(&["red", "git", "--no-tree"]),
        "internet/github\ninternet/reddit\n"
    );
    assert_eq!(
        fixture.output(&["red", "--print", "--no-tree"]),
        "internet:\n  reddit:\n    password: rdt\n    username: sakis\n"
    );
    assert_eq!(
        fixture.output(&["mail"]),
        ".\n└── group\n    └── google (gmail)\n"
    );
    assert_eq!(
        fixture.output(&["social", "--no-tree"]),
        "internet/social/twitter\n"
    );
    assert_eq!(fixture.output(&["server", "-n"]), "server\n");
    assert_eq!(fixture.output(&["no-such-entry"]), "");
    assert_eq!(fixture.output(&[]), "");
    assert_eq!(fixture.output(&["no-such-entry", "--clip"]), "");
    assert!(!fixture.directory.join("clipboard").exists());

    assert_eq!(
        fixture.output(&["red", "git", "--clip", "--timeout", "0"]),
        ".\n└── internet\n    ├── github\n    └── reddit\n\nCopied password of internet/github to clipboard.\n"
    );
    assert_eq!(
        fs::read_to_string(fixture.directory.join("clipboard")).unwrap(),
        "gh"
    );
    assert_eq!(
        fixture.output(&["mail", "-n", "-c", "-t", "0"]),
        "group/google (gmail)\n\nCopied password of group/google (gmail) to clipboard.\n"
    );
    for term in ["missing", "null_entry"] {
        let output = fixture.run(&[term, "--clip"]);
        assert!(!output.status.success());
        assert_eq!(
            String::from_utf8(output.stderr).unwrap(),
            format!("group/{} does not have a password\n", term)
        );
    }

    fixture
        .configure("color: true\nclip: true\ntimeout: 0\nfind:\n  no_tree: true\n  clip: false\n");
    fs::remove_file(fixture.directory.join("clipboard")).unwrap();
    assert_eq!(fixture.output(&["red", "--no-color"]), "internet/reddit\n");
    assert!(!fixture.directory.join("clipboard").exists());
    assert_eq!(
        fixture.output(&["red", "--clip", "--no-clip"]),
        "internet/reddit\n"
    );
    assert_eq!(
        fixture.output(&["red", "--no-clip", "--clip"]),
        "internet/reddit\n\nCopied password of internet/reddit to clipboard.\n"
    );
    fixture.configure("clip: true\ntimeout: 0\nfind:\n  print_: true\n");
    fs::remove_file(fixture.directory.join("clipboard")).unwrap();
    assert_eq!(
        fixture.output(&["red", "--no-clip"]),
        "internet:\n  reddit:\n    password: rdt\n    username: sakis\n"
    );
    assert!(!fixture.directory.join("clipboard").exists());
    assert!(
        fixture
            .output(&["red", "--no-clip", "--color"])
            .contains("\x1b[")
    );
}
