use std::fs;
use std::os::unix::fs::PermissionsExt;
use std::path::PathBuf;
use std::process::{Command, Output, Stdio};
use std::time::{Duration, Instant, SystemTime, UNIX_EPOCH};

struct Fixture {
    directory: PathBuf,
}

impl Fixture {
    fn new() -> Self {
        let nonce = SystemTime::now()
            .duration_since(UNIX_EPOCH)
            .unwrap()
            .as_nanos();
        let directory = std::env::temp_dir().join(format!(
            "passata-clipboard-{}-{}",
            std::process::id(),
            nonce
        ));
        fs::create_dir(&directory).unwrap();
        fs::write(directory.join("config.yml"), "database: unused\n").unwrap();
        for program in ["pbcopy", "xsel", "wl-copy"] {
            let script = directory.join(program);
            fs::write(
                &script,
                format!(
                    "#!/bin/sh\ncat > \"$PASSATA_TEST_CLIPBOARD\"\nprintf '%s %s\\n' '{program}' \"$*\" >> \"$PASSATA_TEST_LOG\"\nif [ \"${{PASSATA_TEST_EXIT:-0}}\" != 0 ]; then\n  printf 'clipboard backend failed\\n' >&2\nfi\nexit \"${{PASSATA_TEST_EXIT:-0}}\"\n"
                ),
            )
            .unwrap();
            fs::set_permissions(script, fs::Permissions::from_mode(0o700)).unwrap();
        }
        Self { directory }
    }

    fn command(&self, display: &str, session: &str, timeout: &str, fail: bool) -> Command {
        let mut paths = vec![self.directory.clone()];
        paths.extend(std::env::split_paths(&std::env::var_os("PATH").unwrap()));
        let mut command = Command::new(env!("CARGO_BIN_EXE_passata-rs"));
        command
            .env("PATH", std::env::join_paths(paths).unwrap())
            .env("WAYLAND_DISPLAY", display)
            .env("XDG_SESSION_TYPE", session)
            .env("DISPLAY", ":1")
            .env("PASSATA_TEST_LOG", self.directory.join("log"))
            .env("PASSATA_TEST_CLIPBOARD", self.directory.join("clipboard"))
            .env("PASSATA_TEST_EXIT", if fail { "3" } else { "0" })
            .arg("--config")
            .arg(self.directory.join("config.yml"))
            .args(["generate", "--clip", "--print", "--timeout", timeout])
            .stdin(Stdio::null());
        command
    }

    fn run(&self, display: &str, session: &str, timeout: &str, fail: bool) -> Output {
        self.command(display, session, timeout, fail)
            .output()
            .unwrap()
    }

    fn log(&self) -> String {
        fs::read_to_string(self.directory.join("log")).unwrap()
    }
}

impl Drop for Fixture {
    fn drop(&mut self) {
        fs::remove_dir_all(&self.directory).unwrap();
    }
}

#[test]
fn selects_clipboard_backend_and_preserves_password() {
    for (display, session) in [
        ("", "x11"),
        ("", ""),
        ("wayland-1", "wayland"),
        ("wayland-1", "x11"),
        ("", "wayland"),
    ] {
        let fixture = Fixture::new();
        let output = fixture.run(display, session, "0", false);
        assert!(output.status.success(), "{output:?}");
        let expected = if cfg!(target_os = "macos") {
            "pbcopy \n"
        } else if !display.is_empty() || session == "wayland" {
            "wl-copy \n"
        } else {
            "xsel -i -b\n"
        };
        assert_eq!(fixture.log(), expected);
        let password = fs::read_to_string(fixture.directory.join("clipboard")).unwrap();
        assert!(!password.is_empty());
        assert!(
            String::from_utf8(output.stdout)
                .unwrap()
                .lines()
                .any(|line| line == password)
        );
    }
}

#[test]
fn schedules_clearing_on_wayland_and_macos() {
    let fixture = Fixture::new();
    let output = fixture.run("wayland-1", "wayland", "1", false);
    assert!(output.status.success(), "{output:?}");
    let expected = if cfg!(target_os = "macos") {
        "pbcopy \npbcopy \n"
    } else {
        "wl-copy \nwl-copy --clear\n"
    };
    let deadline = Instant::now() + Duration::from_secs(5);
    while fixture.log() != expected && Instant::now() < deadline {
        std::thread::sleep(Duration::from_millis(20));
    }
    assert_eq!(fixture.log(), expected);
}

#[test]
fn exits_while_wayland_owner_keeps_streams_open_and_clears_in_background() {
    if cfg!(target_os = "macos") {
        return;
    }
    let fixture = Fixture::new();
    fs::write(
        fixture.directory.join("wl-copy"),
        "#!/bin/sh\ncat > \"$PASSATA_TEST_CLIPBOARD\"\nprintf 'wl-copy %s\\n' \"$*\" >> \"$PASSATA_TEST_LOG\"\nif [ \"$*\" != '--clear' ]; then\n  sleep 4 &\nfi\n",
    )
    .unwrap();
    let mut child = fixture
        .command("wayland-1", "wayland", "3", false)
        .stdout(Stdio::null())
        .stderr(Stdio::null())
        .spawn()
        .unwrap();
    let deadline = Instant::now() + Duration::from_secs(2);
    let status = loop {
        if let Some(status) = child.try_wait().unwrap() {
            break Some(status);
        }
        if Instant::now() >= deadline {
            child.kill().unwrap();
            child.wait().unwrap();
            break None;
        }
        std::thread::sleep(Duration::from_millis(20));
    };
    assert!(status.is_some_and(|status| status.success()));
    assert_eq!(fixture.log(), "wl-copy \n");
    assert!(
        !fs::read(fixture.directory.join("clipboard"))
            .unwrap()
            .is_empty()
    );

    let deadline = Instant::now() + Duration::from_secs(5);
    while fixture.log() != "wl-copy \nwl-copy --clear\n" && Instant::now() < deadline {
        std::thread::sleep(Duration::from_millis(20));
    }
    assert_eq!(fixture.log(), "wl-copy \nwl-copy --clear\n");
    assert!(
        fs::read(fixture.directory.join("clipboard"))
            .unwrap()
            .is_empty()
    );
}

#[test]
fn schedules_clearing_on_x11() {
    if cfg!(target_os = "macos") {
        return;
    }
    let fixture = Fixture::new();
    let status = fixture
        .command("", "x11", "1", false)
        .stdout(Stdio::null())
        .stderr(Stdio::null())
        .status()
        .unwrap();
    assert!(status.success());
    assert_eq!(fixture.log(), "xsel -i -b\n");
    assert!(
        !fs::read(fixture.directory.join("clipboard"))
            .unwrap()
            .is_empty()
    );

    let expected = "xsel -i -b\nxsel -c -b\n";
    let deadline = Instant::now() + Duration::from_secs(5);
    while fixture.log() != expected && Instant::now() < deadline {
        std::thread::sleep(Duration::from_millis(20));
    }
    assert_eq!(fixture.log(), expected);
    assert!(
        fs::read(fixture.directory.join("clipboard"))
            .unwrap()
            .is_empty()
    );
}

#[test]
fn reports_backend_failure_without_scheduling_clear() {
    let fixture = Fixture::new();
    let output = fixture.run("wayland-1", "wayland", "1", true);
    assert!(!output.status.success());
    let stderr = String::from_utf8(output.stderr).unwrap();
    assert!(stderr.contains("Clipboard command exited"));
    assert!(stderr.contains("clipboard backend failed"));
    std::thread::sleep(Duration::from_millis(1200));
    assert_eq!(fixture.log().lines().count(), 1);
}
