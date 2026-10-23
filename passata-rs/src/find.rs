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

use std::io::IsTerminal;

use clap::ArgMatches;
use pager::Pager;
use yaml_rust::Yaml;

use crate::database::{Database, entry_password};
use crate::output::{clipboard, clipboard_timeout, colorize, render_tree};
use crate::utils::config_setting;

/// Render search results as YAML, full paths, or a tree, with YAML taking precedence.
fn render_matches(
    matches: &Database,
    print: bool,
    no_tree: bool,
    color: bool,
) -> Result<String, String> {
    if matches.db.as_hash().is_none_or(|map| map.is_empty()) {
        return Ok(String::new());
    }
    if print {
        let yaml = matches.yaml_for(&matches.db)?;
        let yaml = yaml.trim();
        Ok(if color {
            colorize(yaml)
        } else {
            yaml.to_owned()
        })
    } else if no_tree {
        Ok(matches.paths().join("\n"))
    } else {
        Ok(render_tree(&matches.db, ".", color))
    }
}

/// Read the first result's path and password, rejecting missing or null passwords.
fn first_password(matches: &Database) -> Result<Option<(String, String)>, String> {
    let Some((path, entry)) = matches.entries().into_iter().next() else {
        return Ok(None);
    };
    let password = entry_password(entry, &path)?;
    Ok(Some((path, password)))
}

/// Search and display entries using CLI/configuration options, optionally copying the first password.
pub fn find(
    db: &Database,
    args: &ArgMatches,
    config: Option<&Yaml>,
    root_config: &Yaml,
) -> Result<(), String> {
    let flag = |key: &str| args.get_flag(key);
    let names: Vec<_> = args
        .get_many::<String>("names")
        .map(|names| names.cloned().collect())
        .unwrap_or_default();
    let matches = db.find(&names)?;
    let clip = flag("clip") && !flag("no_clip");
    let mut pager = Pager::new();
    if !clip {
        pager.setup();
    }
    let color = if flag("color") || flag("no_color") {
        flag("color")
    } else {
        crate::config_value(root_config, "color")
            .and_then(Yaml::as_bool)
            .unwrap_or_else(|| {
                if clip {
                    std::io::stdout().is_terminal()
                } else {
                    pager.is_on()
                }
            })
    };
    let print = flag("print");
    let output = render_matches(&matches, print, flag("no_tree"), color)?;
    if print || !output.is_empty() {
        println!("{}", output);
    }
    if clip {
        if let Some((path, password)) = first_password(&matches)? {
            let configured =
                config_setting(config, root_config, "timeout").and_then(crate::yaml_u64);
            clipboard(&password, clipboard_timeout(args, configured))?;
            println!("\nCopied password of {} to clipboard.", path);
        }
    }
    Ok(())
}

#[cfg(test)]
#[path = "../tests/unit/find_unit.rs"]
mod tests;
