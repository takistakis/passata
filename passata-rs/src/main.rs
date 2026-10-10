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

mod config_editor;
mod database;
mod find;
mod generate;
mod init;
mod insert;
mod ls;
mod mv;
mod output;
mod rm;
mod show;
mod tree;
mod utils;
mod yaml;

use std::convert::TryFrom;
use std::path::PathBuf;

use clap::{Arg, ArgAction, Command, ValueHint};
use yaml_rust::{Yaml, YamlLoader};

use crate::database::DatabaseHooks;
use crate::find::find;
use crate::generate::generate;
use crate::ls::ls;
use crate::show::show;
use crate::tree::tree;

/// Define the CLI commands, option defaults, value parsers, and override relationships.
pub fn cli() -> Command {
    Command::new("passata")
        .version("0.2.0")
        .author("Panagiotis Ktistakis <panktist@gmail.com>")
        .about("A simple password manager, inspired by pass")
        .subcommand_required(true)
        .disable_help_subcommand(true)
        .arg(
            Arg::new("config")
                .long("config")
                .help("Path of the configuration file.")
                .value_name("PATH")
                .value_hint(ValueHint::FilePath)
                .global(true),
        )
        .arg(
            Arg::new("color")
                .long("color")
                .help("Colorize the output.")
                .action(ArgAction::SetTrue)
                .overrides_with("no_color")
                .global(true),
        )
        .arg(
            Arg::new("no_color")
                .long("no-color")
                .help("Do not colorize the output.")
                .action(ArgAction::SetTrue)
                .overrides_with("color")
                .global(true),
        )
        .subcommand(
            Command::new("init")
                .about("Initialize password database.")
                .arg(
                    Arg::new("force")
                        .short('f')
                        .long("force")
                        .action(ArgAction::SetTrue)
                        .help("Do not prompt for confirmation."),
                )
                .arg(
                    Arg::new("gpg_id")
                        .short('g')
                        .long("gpg-id")
                        .value_name("GPG_ID")
                        .help("GnuPG ID for database encryption."),
                )
                .arg(
                    Arg::new("path")
                        .short('p')
                        .long("path")
                        .value_name("PATH")
                        .value_hint(ValueHint::FilePath)
                        .help("Database path."),
                ),
        )
        .subcommand(
            Command::new("config")
                .about("Edit the configuration file.")
                .arg(
                    Arg::new("editor")
                        .short('e')
                        .long("editor")
                        .value_name("EDITOR")
                        .help("Which editor to use."),
                ),
        )
        .subcommand(
            Command::new("ls")
                .about("List entries in the database or a group.")
                .arg(Arg::new("group").help("List only entries of the given group.")),
        )
        .subcommand(
            Command::new("tree")
                .about("List entries in a tree-like format.")
                .arg(Arg::new("group").help("Show only the given group.")),
        )
        .subcommand(
            Command::new("find")
                .about("List matching entries in a tree-like format.")
                .arg(Arg::new("names").num_args(0..).help("Search terms for entry paths or keywords."))
                .arg(
                    Arg::new("no_tree")
                        .short('n')
                        .long("no-tree")
                        .action(ArgAction::SetTrue)
                        .help("Print entries as full paths."),
                )
                .arg(
                    Arg::new("print")
                        .short('p')
                        .long("print")
                        .action(ArgAction::SetTrue)
                        .help("Show the found entries."),
                )
                .arg(
                    Arg::new("clip")
                        .short('c')
                        .long("clip")
                        .action(ArgAction::SetTrue)
                        .overrides_with("no_clip")
                        .help("Copy the first result's password to clipboard."),
                )
                .arg(
                    Arg::new("no_clip")
                        .short('C')
                        .long("no-clip")
                        .action(ArgAction::SetTrue)
                        .overrides_with("clip")
                        .help("Do not copy a password to clipboard."),
                )
                .arg(
                    Arg::new("timeout")
                        .short('t')
                        .long("timeout")
                        .default_value("45")
                        .value_parser(clap::value_parser!(u64))
                        .help("Number of seconds until the clipboard is cleared."),
                ),
        )
        .subcommand(
            Command::new("show")
                .about("Show entry, group or the whole database.")
                .arg(
                    Arg::new("name")
                        .help("Entry or group to show.")
                        .required(false),
                )
                .arg(
                    Arg::new("clip")
                        .short('c')
                        .long("clip")
                        .action(ArgAction::SetTrue)
                        .overrides_with("no_clip")
                        .help("Copy password to clipboard."),
                )
                .arg(
                    Arg::new("no_clip")
                        .short('C')
                        .long("no-clip")
                        .action(ArgAction::SetTrue)
                        .overrides_with("clip")
                        .help("Print instead of copying the password."),
                )
                .arg(
                    Arg::new("timeout")
                        .short('t')
                        .long("timeout")
                        .default_value("45")
                        .value_parser(clap::value_parser!(u64))
                        .help("Number of seconds until the clipboard is cleared."),
                ),
        )
        .subcommand(
            Command::new("generate")
                .about("Generate a random password.")
                .long_about(
                    "Generate a random password.\n\nWhen overwriting an existing entry, the old password is kept in <old_password>.",
                )
                .arg(Arg::new("name").help("Entry to generate a password for."))
                .arg(
                    Arg::new("force")
                        .short('f')
                        .long("force")
                        .action(ArgAction::SetTrue)
                        .help("Do not prompt for confirmation."),
                )
                .arg(
                    Arg::new("print")
                        .short('p')
                        .long("print")
                        .action(ArgAction::SetTrue)
                        .overrides_with("no_print")
                        .help("Print the password."),
                )
                .arg(
                    Arg::new("no_print")
                        .short('P')
                        .long("no-print")
                        .action(ArgAction::SetTrue)
                        .overrides_with("print")
                        .help("Do not print the password."),
                )
                .arg(
                    Arg::new("clip")
                        .short('c')
                        .long("clip")
                        .action(ArgAction::SetTrue)
                        .overrides_with("no_clip")
                        .help("Copy password to clipboard."),
                )
                .arg(
                    Arg::new("no_clip")
                        .short('C')
                        .long("no-clip")
                        .action(ArgAction::SetTrue)
                        .overrides_with("clip")
                        .help("Do not copy password to clipboard."),
                )
                .arg(
                    Arg::new("timeout")
                        .short('t')
                        .long("timeout")
                        .default_value("45")
                        .value_parser(clap::value_parser!(u64))
                        .help("Number of seconds until the clipboard is cleared."),
                )
                .arg(
                    Arg::new("length")
                        .short('l')
                        .long("length")
                        .default_value("20")
                        .value_parser(clap::value_parser!(u32).range(1..))
                        .value_name("INTEGER")
                        .help("Length of the generated password."),
                )
                .arg(
                    Arg::new("entropy")
                        .short('e')
                        .long("entropy")
                        .value_parser(clap::value_parser!(f64))
                        .help(
                            "Calculate length for given minimum bits of entropy (takes precedence over --length).",
                        ),
                )
                .arg(
                    Arg::new("charset")
                        .short('s')
                        .long("charset")
                        .default_value("full")
                        .value_parser(["letters", "digits", "alnum", "full"])
                        .ignore_case(true)
                        .help("Character set for password generation."),
                )
                .arg(
                    Arg::new("wordlist")
                        .short('w')
                        .long("wordlist")
                        .value_name("NAME_OR_PATH")
                        .help("Generate a passphrase using a wordlist."),
                ),
        )
        .subcommand(
            Command::new("insert")
                .about("Insert a new password.")
                .long_about(
                    "Insert a new password.\n\nWhen overwriting an existing entry, the old password is kept in <old_password>.",
                )
                .arg(
                    Arg::new("name")
                        .required(true)
                        .help("Entry to insert a password for."),
                )
                .arg(
                    Arg::new("force")
                        .short('f')
                        .long("force")
                        .action(ArgAction::SetTrue)
                        .help("Do not prompt for confirmation."),
                )
                .arg(
                    Arg::new("password")
                        .long("password")
                        .value_name("PASSWORD")
                        .help("Give password instead of being prompted for it."),
                ),
        )
        .subcommand(
            Command::new("rm")
                .about("Remove entries or groups.")
                .arg(
                    Arg::new("names")
                        .value_name("ENTRY/GROUP")
                        .num_args(1..)
                        .required(true),
                )
                .arg(
                    Arg::new("force")
                        .short('f')
                        .long("force")
                        .action(ArgAction::SetTrue)
                        .help("Do not prompt for confirmation."),
                )
                .arg(
                    Arg::new("recursive")
                        .short('r')
                        .long("recursive")
                        .action(ArgAction::SetTrue)
                        .help("Remove groups recursively."),
                ),
        )
        .subcommand(
            Command::new("mv")
                .about("Move or rename entries.")
                .long_about("Rename SOURCE to DEST or move SOURCE(s) to GROUP.")
                .arg(
                    Arg::new("source")
                        .value_name("SOURCE")
                        .num_args(1..)
                        .required(true),
                )
                .arg(
                    Arg::new("dest")
                        .value_name("DEST/GROUP")
                        .required(true),
                )
                .arg(
                    Arg::new("force")
                        .short('f')
                        .long("force")
                        .action(ArgAction::SetTrue)
                        .help("Do not prompt for confirmation."),
                ),
        )
}

/// Prefer `PASSATA_CONFIG_PATH`, otherwise use `~/.passata/config.yml` or a local fallback.
fn default_config_path() -> PathBuf {
    if let Some(path) = std::env::var_os("PASSATA_CONFIG_PATH") {
        return PathBuf::from(path);
    }
    std::env::var_os("HOME")
        .map(|home| PathBuf::from(home).join(".passata"))
        .unwrap_or_else(|| PathBuf::from(".passata"))
        .join("config.yml")
}

/// Expand `~` and `~/` using `HOME`, leaving other paths or a missing home unchanged.
fn expand_home(path: &str) -> PathBuf {
    if path == "~" {
        return std::env::var_os("HOME")
            .map(PathBuf::from)
            .unwrap_or_else(|| PathBuf::from(path));
    }
    if let Some(rest) = path.strip_prefix("~/") {
        return std::env::var_os("HOME")
            .map(|home| PathBuf::from(home).join(rest))
            .unwrap_or_else(|| PathBuf::from(path));
    }
    PathBuf::from(path)
}

/// Load one YAML configuration mapping, treating an empty file as an empty mapping.
fn load_config(path: &PathBuf) -> Result<Yaml, String> {
    let contents =
        std::fs::read_to_string(path).map_err(|_| String::from("Run `passata init` first"))?;
    let mut documents = YamlLoader::load_from_str(&contents)
        .map_err(|e| format!("Invalid configuration YAML: {}", e))?;
    if documents.len() > 1 {
        return Err(String::from(
            "Invalid configuration YAML: multiple documents",
        ));
    }
    if documents.is_empty() {
        return Ok(Yaml::Hash(Default::default()));
    }
    let config = documents.remove(0);
    if !matches!(config, Yaml::Hash(_)) {
        return Err(String::from("Invalid configuration"));
    }
    Ok(config)
}

/// Look up a string key in a configuration mapping.
fn config_value<'a>(config: &'a Yaml, key: &str) -> Option<&'a Yaml> {
    config
        .as_hash()
        .and_then(|map| map.get(&Yaml::String(key.to_owned())))
}

/// Read a nonnegative integer setting from a YAML integer or numeric string.
fn yaml_u64(value: &Yaml) -> Option<u64> {
    value
        .as_i64()
        .and_then(|number| u64::try_from(number).ok())
        .or_else(|| value.as_str().and_then(|number| number.parse().ok()))
}

/// Load configuration and dispatch the CLI command, exiting with an error on failure.
fn main() {
    let matches = cli().get_matches();
    let config_path = matches
        .get_one::<String>("config")
        .map(|path| expand_home(path))
        .unwrap_or_else(default_config_path);
    if let Some(("init", args)) = matches.subcommand() {
        if let Err(error) = init::initialize(&config_path, args) {
            eprintln!("{}", error);
            std::process::exit(1);
        }
        return;
    }
    let config = match load_config(&config_path) {
        Ok(config) => config,
        Err(error) => {
            eprintln!("{}", error);
            std::process::exit(1);
        }
    };
    let command_name = matches.subcommand_name().unwrap_or_default();
    let command_config = config_value(&config, command_name);
    if command_config.is_some_and(|value| !matches!(value, Yaml::Hash(_))) {
        eprintln!("Invalid configuration for command {}", command_name);
        std::process::exit(1);
    }
    let database_value = config_value(&config, "database");
    let database_path = match database_value.and_then(Yaml::as_str) {
        Some(path) => expand_home(path),
        None => {
            eprintln!(
                "Value for database ({}) is not a valid string",
                database_value
                    .map(|value| format!("{:?}", value))
                    .unwrap_or_else(|| String::from("None"))
            );
            std::process::exit(1);
        }
    };
    let gpg_id = config_value(&config, "gpg_id")
        .and_then(Yaml::as_str)
        .unwrap_or_default()
        .to_owned();
    let database_path = database_path.to_string_lossy().into_owned();
    let mut hooks = DatabaseHooks::new(&config_path);

    let result = match matches.subcommand() {
        Some(("config", sub_matches)) => {
            config_editor::edit(&config_path, sub_matches, command_config, &config)
        }
        Some(("ls", sub_matches)) => hooks.read(&database_path, false).and_then(|db| {
            ls(
                &db,
                sub_matches,
                config_value(&config, "color").and_then(Yaml::as_bool),
            )
        }),
        Some(("tree", sub_matches)) => hooks.read(&database_path, false).and_then(|db| {
            tree(
                &db,
                sub_matches,
                config_value(&config, "color").and_then(Yaml::as_bool),
            )
        }),
        Some(("show", sub_matches)) => hooks.read(&database_path, false).and_then(|db| {
            show(
                &db,
                sub_matches,
                config_value(&config, "color").and_then(Yaml::as_bool),
                command_config
                    .and_then(|command| config_value(command, "timeout"))
                    .or_else(|| config_value(&config, "timeout"))
                    .and_then(yaml_u64),
            )
        }),
        Some(("find", sub_matches)) => hooks
            .read(&database_path, false)
            .and_then(|db| find(&db, sub_matches, command_config, &config)),
        Some(("generate", sub_matches)) => generate(
            &database_path,
            sub_matches,
            command_config,
            &config,
            &gpg_id,
            &mut hooks,
        ),
        Some(("insert", sub_matches)) => insert::insert(
            &database_path,
            sub_matches,
            command_config,
            &config,
            &gpg_id,
            &mut hooks,
        ),
        Some(("mv", sub_matches)) => mv::mv(
            &database_path,
            sub_matches,
            command_config,
            &config,
            &gpg_id,
            &mut hooks,
        ),
        Some(("rm", sub_matches)) => rm::rm(
            &database_path,
            sub_matches,
            command_config,
            &config,
            &gpg_id,
            &mut hooks,
        ),
        _ => Ok(()),
    };
    if let Err(error) = &result {
        eprintln!("{}", error);
    }
    // Like Python's atexit callbacks, hook failures are reported without changing the exit status.
    if let Err(error) = hooks.finish() {
        eprintln!("{}", error);
    }
    drop(hooks);
    if result.is_err() {
        std::process::exit(1);
    }
}

#[cfg(test)]
#[path = "../tests/unit/cli_tests.rs"]
mod tests;
