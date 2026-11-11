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

use std::io::{self, IsTerminal, Write};
use std::path::PathBuf;

use rand::RngExt;

use crate::database::DatabaseHooks;
use crate::insert::confirm_overwrite;
use crate::output::{DEFAULT_TIMEOUT, clipboard};
use crate::utils::confirm;

const ENTROPY_WARNING_THRESHOLD: f64 = 32.0;

/// Resolve a case-insensitive character-set name to its ASCII generation pool.
fn charset(name: &str) -> Result<&'static str, String> {
    match name.to_lowercase().as_str() {
        "letters" => Ok("abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ"),
        "digits" => Ok("0123456789"),
        "alnum" => Ok("abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789"),
        "full" => Ok(
            "abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789!\"#$%&'()*+,-./:;<=>?@[\\]^_`{|}~",
        ),
        _ => Err(format!("Invalid charset '{}'", name)),
    }
}

/// Return bundled and system wordlist directories in lookup order.
fn wordlist_dirs() -> Vec<PathBuf> {
    vec![
        PathBuf::from(env!("CARGO_MANIFEST_DIR")).join("../wordlists"),
        PathBuf::from("/usr/local/share/passata"),
        PathBuf::from("/usr/share/passata"),
    ]
}

/// Resolve an existing path or installed wordlist name, listing alternatives on failure.
fn resolve_wordlist(value: &str) -> Result<PathBuf, String> {
    let path = crate::expand_home(value);
    if path.exists() {
        return Ok(path);
    }

    let dirs = wordlist_dirs();
    for directory in &dirs {
        for candidate in [
            directory.join(value),
            directory.join(format!("{}.txt", value)),
        ] {
            if candidate.exists() {
                return Ok(candidate);
            }
        }
    }
    let mut names = Vec::new();
    for directory in dirs {
        if let Ok(entries) = std::fs::read_dir(directory) {
            let mut paths: Vec<_> = entries.flatten().map(|entry| entry.path()).collect();
            paths.sort();
            for path in paths {
                if path.extension().and_then(|extension| extension.to_str()) == Some("txt") {
                    if let Some(stem) = path.file_stem().and_then(|stem| stem.to_str()) {
                        if !names.iter().any(|known| known == stem) {
                            names.push(stem.to_owned());
                        }
                    }
                }
            }
        }
    }
    let hint = if names.is_empty() {
        String::new()
    } else {
        format!(" Available: {}", names.join(", "))
    };
    Err(format!("Wordlist '{}' not found.{}", value, hint))
}

/// Generate characters or words using a length or minimum entropy target.
///
/// Reject invalid pools and sizes, and return `None` if low-entropy confirmation is declined.
fn generate_password(
    length: u64,
    entropy: Option<f64>,
    charset_name: &str,
    wordlist: Option<&str>,
    force: bool,
) -> Result<Option<String>, String> {
    let words = if let Some(wordlist) = wordlist {
        let path = resolve_wordlist(wordlist)?;
        let data =
            std::fs::read_to_string(&path).map_err(|e| format!("{}: {}", path.display(), e))?;
        // Empty pieces between "\r\n" are dropped by the blank-word filter.
        Some(
            data.split([
                '\n', '\r', '\u{b}', '\u{c}', '\u{1c}', '\u{1d}', '\u{1e}', '\u{85}', '\u{2028}',
                '\u{2029}',
            ])
            .filter(|word| !word.trim().is_empty())
            .map(str::to_owned)
            .collect::<Vec<_>>(),
        )
    } else {
        None
    };

    let pool = if words.is_none() {
        charset(charset_name)?
    } else {
        ""
    };
    let pool_size = words.as_ref().map_or(pool.len(), Vec::len);
    if pool_size == 0 {
        return Err(String::from("The selected password pool is empty"));
    }
    if entropy.is_some_and(|value| !value.is_finite() || value <= 0.0) {
        return Err(String::from("Entropy must be a finite positive number"));
    }
    if entropy.is_some() && pool_size == 1 {
        return Err(String::from(
            "Cannot calculate password length for a one-item pool",
        ));
    }
    let count = if let Some(entropy) = entropy {
        let count = (entropy / (pool_size as f64).log2()).ceil();
        if !count.is_finite() || count >= isize::MAX as f64 {
            return Err(String::from("Requested entropy is too large"));
        }
        count as u64
    } else {
        length
    };
    if count == 0 {
        return Err(String::from("Password length must be greater than zero"));
    }
    let actual_entropy = (count as f64) * (pool_size as f64).log2();
    if actual_entropy < ENTROPY_WARNING_THRESHOLD {
        let message = format!(
            "Generate password with only {:.3} bits of entropy?",
            actual_entropy
        );
        if !confirm(&message, force)? {
            return Ok(None);
        }
    }

    let password = if let Some(words) = words {
        let mut rng = rand::rng();
        (0..count)
            .map(|_| words[rng.random_range(0..words.len())].as_str())
            .collect::<Vec<_>>()
            .join(" ")
    } else {
        let pool = pool.as_bytes();
        let mut rng = rand::rng();
        (0..count)
            .map(|_| pool[rng.random_range(0..pool.len())] as char)
            .collect()
    };
    println!(
        "Generated password with {:.3} bits of entropy",
        actual_entropy
    );
    Ok(Some(password))
}

/// Check whether an option was explicitly supplied rather than filled by a default.
fn source_is_cli(args: &clap::ArgMatches, key: &str) -> bool {
    args.value_source(key) == Some(clap::parser::ValueSource::CommandLine)
}

/// Display a continuation prompt and wait for a line of input.
fn pause() -> Result<(), String> {
    if !io::stdin().is_terminal() || !io::stdout().is_terminal() {
        return Ok(());
    }
    print!("Press any key to continue ...");
    io::stdout()
        .flush()
        .map_err(|e| format!("Failed to flush stdout: {}", e))?;
    let mut input = String::new();
    io::stdin()
        .read_line(&mut input)
        .map_err(|e| format!("Failed to read from stdin: {}", e))?;
    println!();
    Ok(())
}

/// Resolve generation options, optionally save the password, and print or copy it.
///
/// Named entries are updated under an exclusive lock after overwrite confirmation.
pub fn generate(
    database_path: &str,
    args: &clap::ArgMatches,
    gpg_id: &str,
    hooks: &mut DatabaseHooks,
) -> Result<(), String> {
    let force = args.get_flag("force");
    let length = *args.get_one::<u64>("length").unwrap_or(&20);
    let mut entropy = args.get_one::<f64>("entropy").copied();
    let charset_name = args
        .get_one::<String>("charset")
        .map(String::as_str)
        .unwrap_or("full");
    let mut wordlist = args.get_one::<String>("wordlist").map(String::as_str);

    if source_is_cli(args, "length") && !source_is_cli(args, "entropy") {
        entropy = None;
    }
    if source_is_cli(args, "charset") && !source_is_cli(args, "wordlist") {
        wordlist = None;
    }

    let Some(password) = generate_password(length, entropy, charset_name, wordlist, force)? else {
        return Ok(());
    };
    let name = args
        .get_one::<String>("name")
        .map(String::as_str)
        .filter(|name| !name.is_empty());
    let clip = args.get_flag("clip") && !args.get_flag("no_clip");
    if let Some(name) = name {
        let mut db = hooks.read(database_path, true)?;
        if !confirm_overwrite(&db, name, force, confirm)? {
            return Ok(());
        }
        let old_password = db.insert_password(name, &password)?;
        hooks.write(&mut db, gpg_id)?;
        if clip {
            if let Some(old) = &old_password {
                clipboard(old, 0)?;
                println!("Copied old password to clipboard.");
                pause()?;
            }
        }
    }

    let print_password =
        (args.get_flag("print") && !args.get_flag("no_print")) || (name.is_none() && !clip);
    if print_password {
        println!("{}", password);
    }
    if clip {
        let timeout = args.get_one::<u64>("timeout").copied();
        clipboard(&password, timeout.unwrap_or(DEFAULT_TIMEOUT))?;
        println!("Copied generated password to clipboard.");
    }
    Ok(())
}

#[cfg(test)]
#[path = "../tests/unit/generate.rs"]
mod tests;
