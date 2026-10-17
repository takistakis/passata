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

use pager::Pager;
use yaml_rust::Yaml;

use crate::database::Database;
use crate::output::{clipboard, colorize};
use crate::utils::scalar_string;

/// Display a selected node as YAML or copy an entry's non-null password to the clipboard.
pub fn show(
    db: &Database,
    args: &clap::ArgMatches,
    configured_color: Option<bool>,
    configured_timeout: Option<u64>,
) -> Result<(), String> {
    let name = args.get_one::<String>("name").map(String::as_str);
    let entry = db.get(name)?;

    if args.get_flag("clip") {
        let Some(name) = name else {
            return Err(String::from("Can't put the entire database to clipboard"));
        };
        if !matches!(entry, Yaml::Hash(_))
            || matches!(entry, Yaml::Hash(map) if map.values().all(|v| matches!(v, Yaml::Hash(_))))
        {
            return Err(String::from("Can't put a group to clipboard"));
        }
        let password = entry
            .as_hash()
            .and_then(|map| map.get(&Yaml::String(String::from("password"))))
            .ok_or_else(|| format!("{} does not have a password", name))?;
        if matches!(password, Yaml::Null) {
            return Err(format!("{} does not have a password", name));
        }
        let password = scalar_string(password);
        let timeout =
            if args.value_source("timeout") == Some(clap::parser::ValueSource::CommandLine) {
                *args.get_one::<u64>("timeout").unwrap_or(&45)
            } else {
                configured_timeout.unwrap_or(45)
            };
        clipboard(&password, timeout)?;
        return Ok(());
    }

    let output = db.yaml_for(entry)?;
    let output = output.trim();
    let mut pager = Pager::new();
    pager.setup();
    let forced_color = args.get_flag("color") || configured_color == Some(true);
    let no_color = args.get_flag("no_color") || configured_color == Some(false);
    let output = if forced_color || (!no_color && pager.is_on()) {
        colorize(output)
    } else {
        output.to_owned()
    };
    if !output.is_empty() {
        println!("{}", output);
    }
    Ok(())
}
