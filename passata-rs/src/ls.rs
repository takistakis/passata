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

use nu_ansi_term::Color::Blue;
use pager::Pager;

use crate::database::Database;
use crate::output::pager_color;

/// Join child names on separate lines, optionally coloring groups in bold blue.
fn format_items(items: &[(String, bool)], color: bool) -> String {
    items
        .iter()
        .map(|(name, is_group)| {
            if *is_group && color {
                Blue.bold().paint(name.as_str()).to_string()
            } else {
                name.clone()
            }
        })
        .collect::<Vec<_>>()
        .join("\n")
}

/// List a selected group's immediate children through the pager with optional colors.
pub fn ls(
    db: &Database,
    args: &clap::ArgMatches,
    configured_color: Option<bool>,
) -> Result<(), String> {
    let group = args.get_one::<String>("group").map(String::as_str);
    let items = db.group_items(group)?;
    if items.is_empty() {
        return Ok(());
    }

    let mut pager = Pager::new();
    pager.setup();
    let color = pager_color(args, configured_color, pager.is_on());
    let output = format_items(&items, color);
    println!("{}", output);
    Ok(())
}

#[cfg(test)]
#[path = "../tests/unit/ls.rs"]
mod tests;
